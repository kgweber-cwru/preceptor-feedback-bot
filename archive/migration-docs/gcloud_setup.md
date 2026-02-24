# Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Internet                              │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ HTTPS
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Cloud Run Service                         │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Container (Docker)                                     │ │
│  │  ┌──────────────────────────────────────────────────┐  │ │
│  │  │  Streamlit App (app.py)                          │  │ │
│  │  │  - Serves web UI                                 │  │ │
│  │  │  - Handles user sessions                         │  │ │
│  │  │  - Manages conversation state                    │  │ │
│  │  └──────────────────────────────────────────────────┘  │ │
│  │                        │                                │ │
│  │                        │ calls                          │ │
│  │                        ▼                                │ │
│  │  ┌──────────────────────────────────────────────────┐  │ │
│  │  │  VertexAIClient                                  │  │ │
│  │  │  - google-genai SDK                              │  │ │
│  │  └──────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                         │
                         │ Authenticated API calls
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Vertex AI (same GCP project)                    │
│  - Gemini models                                             │
│  - (Future: Claude models)                                   │
└─────────────────────────────────────────────────────────────┘
                         │
                         │ Writes logs
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Cloud Storage Bucket                            │
│  - Application logs (app_YYYYMMDD.log)                       │
│  - Conversation logs (conversation_*.json)                   │
└─────────────────────────────────────────────────────────────┘
```

# Part 3: GCP Infrastructure Setup**

Run these commands in your terminal:
## 1. Create Cloud Storage Bucket for Logs

```bash# Create buckets
gsutil mb -p meded-gcp-sandbox -c STANDARD -l us-central1 gs://meded-feedback-bot-logs
gsutil mb -p meded-gcp-sandbox -c STANDARD -l us-central1 gs://meded-gcp-sandbox_cloudbuild

# Verify it was created
gsutil ls
```

## 2. Enable Required APIs

```bash# Enable Cloud Run API
gcloud services enable run.googleapis.com --project=meded-gcp-sandbox

# Enable Container Registry
gcloud services enable containerregistry.googleapis.com --project=meded-gcp-sandbox

# Enable Vertex AI (should already be enabled)
gcloud services enable aiplatform.googleapis.com --project=meded-gcp-sandbox

# Enable Cloud Storage (should already be enabled)
gcloud services enable storage.googleapis.com --project=meded-gcp-sandbox
```


## 3. Create Service Account for Cloud Run

```bash# Create service account
gcloud iam service-accounts create preceptor-feedback-bot \
    --description="Service account for Preceptor Feedback Bot" \
    --display-name="Preceptor Feedback Bot" \
    --project=meded-gcp-sandbox

# Grant Vertex AI permissions
gcloud projects add-iam-policy-binding meded-gcp-sandbox \
    --member="serviceAccount:preceptor-feedback-bot@meded-gcp-sandbox.iam.gserviceaccount.com" \
    --role="roles/aiplatform.user"

# Grant Cloud Storage permissions
gcloud projects add-iam-policy-binding meded-gcp-sandbox \
    --member="serviceAccount:preceptor-feedback-bot@meded-gcp-sandbox.iam.gserviceaccount.com" \
    --role="roles/storage.objectAdmin"

# Verify permissions
gcloud projects get-iam-policy meded-gcp-sandbox \
    --flatten="bindings[].members" \
    --filter="bindings.members:preceptor-feedback-bot@meded-gcp-sandbox.iam.gserviceaccount.com"
```

---

## Part 4: Install Cloud Code Extension in VS Code

### **1. Install Extension**

1. Open VS Code
2. Click Extensions icon (or Cmd+Shift+X)
3. Search for "Cloud Code"
4. Click "Install" on "Cloud Code" by Google Cloud
5. Wait for installation to complete
6. Reload VS Code if prompted

### **2. Sign in to Google Cloud**

1. Click the Cloud Code icon in the left sidebar (looks like a cloud)
2. Click "Sign in to Google Cloud"
3. Follow the browser authentication flow
4. Select your Google account
5. Grant permissions
6. Return to VS Code

### **3. Set Active Project**

1. In Cloud Code sidebar, click the project dropdown
2. Select "meded-gcp-sandbox"
3. Verify it's set correctly

---

## Part 5: Deploy Using Cloud Code Extension

### **First Deployment**

1. **Open Command Palette**
   - Mac: Cmd+Shift+P
   - Windows/Linux: Ctrl+Shift+P

2. **Type and select:** `Cloud Code: Deploy to Cloud Run`

3. **Configuration wizard will appear:**
   
   **Step 1: Build Settings**
   - Build environment: Select "Cloud Build"
   - Dockerfile: Should auto-detect `./Dockerfile`
   - Click "Next"
   
   **Step 2: Service Settings**
   - Service name: `preceptor-feedback-bot`
   - Region: `us-central1`
   - Platform: "Managed"
   - Click "Next"
   
   **Step 3: Revision Settings**
   - Authentication: "Allow unauthenticated invocations"
   - CPU: 1
   - Memory: 2 GiB
   - Maximum instances: 10
   - Timeout: 300 seconds
   - Service account: `preceptor-feedback-bot@meded-gcp-sandbox.iam.gserviceaccount.com`
   - Click "Next"
   
   **Step 4: Environment Variables**
   Click "Add variable" for each:
```
   DEPLOYMENT_ENV=cloud
   GCP_PROJECT_ID=meded-gcp-sandbox
   GCP_REGION=us-central1
   MODEL_NAME=gemini-2.0-flash-exp
   TEMPERATURE=0.7
   MAX_OUTPUT_TOKENS=2048
   MAX_TURNS=10
   LOG_TO_FILE=true
   LOG_BUCKET=meded-feedback-bot-logs
   LOG_LEVEL=INFO
   REQUIRE_AUTH=false
```
   
   **Step 5: Review and Deploy**
   - Review all settings
   - Click "Deploy"

Deployment didn't go well through the shiny tool. Here's the CLI command for the first deployment:

```bash
# From your project directory, run:
gcloud run deploy preceptor-feedback-bot \
  --source . \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --service-account preceptor-feedback-bot@meded-gcp-sandbox.iam.gserviceaccount.com \
  --set-env-vars "DEPLOYMENT_ENV=cloud,GCP_PROJECT_ID=meded-gcp-sandbox,GCP_REGION=us-central1,MODEL_NAME=gemini-2.0-flash-exp,TEMPERATURE=0.7,MAX_OUTPUT_TOKENS=2048,MAX_TURNS=10,LOG_TO_FILE=true,LOG_BUCKET=meded-feedback-bot-logs,LOG_LEVEL=INFO,REQUIRE_AUTH=false" \
  --memory 2Gi \
  --cpu 1 \
  --timeout 300 \
  --max-instances 10 \
  --project meded-gcp-sandbox
  ```

**subsequent deployments**

```bash
gcloud run deploy preceptor-feedback-bot \
  --source . \
  --region us-central1 \
  --project meded-gcp-sandbox
  ```

4. **Watch Progress**
   - Output panel will show build progress
   - First deployment takes 3-5 minutes
   - You'll see:
     - Building Docker image
     - Pushing to Container Registry
     - Deploying to Cloud Run
     - Service URL when complete

5. **Get Your URL**
   - When complete, you'll see something like:
```
Service [preceptor-feedback-bot] revision [preceptor-feedback-bot-00001-f8m] has been deployed and is serving 100 percent of traffic.
Service URL: https://preceptor-feedback-bot-450703468039.us-central1.run.app
```