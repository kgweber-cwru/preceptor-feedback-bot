# Deployment Guide

This guide covers deploying the Preceptor Feedback Bot to Google Cloud Run.

## Prerequisites

1. **Google Cloud Project** with billing enabled
2. **gcloud CLI** installed and configured
3. **Required APIs enabled:**
   ```bash
   gcloud services enable run.googleapis.com \
     cloudbuild.googleapis.com \
     firestore.googleapis.com \
     aiplatform.googleapis.com \
     storage.googleapis.com \
     secretmanager.googleapis.com
   ```

## One-Time Setup

### 1. Create Firestore Database

```bash
# Create Firestore database (if not already created)
gcloud firestore databases create --region=us-central1
```

### 2. Deploy Firestore Indexes

You have three options for creating Firestore indexes:

#### Option A: Let Firestore Auto-Create (Easiest for Testing)

**Recommended for first deployment.** Just deploy the app and use it. When a query needs an index, Firestore will return an error with a clickable link to create it automatically.

1. Deploy your app (skip to step 3)
2. Try loading the dashboard
3. If you get an index error, click the provided URL
4. Firestore creates the index for you

#### Option B: Manual gcloud Commands

Create each index individually:

```bash
# Index 1: conversations by user_id + updated_at
gcloud firestore indexes composite create \
  --collection-group=conversations \
  --query-scope=COLLECTION \
  --field-config=field-path=user_id,order=ASCENDING \
  --field-config=field-path=updated_at,order=DESCENDING

# Index 2: conversations by user_id + status + updated_at
gcloud firestore indexes composite create \
  --collection-group=conversations \
  --query-scope=COLLECTION \
  --field-config=field-path=user_id,order=ASCENDING \
  --field-config=field-path=status,order=ASCENDING \
  --field-config=field-path=updated_at,order=DESCENDING

# Index 3: feedback by conversation_id (single field - may auto-create)
gcloud firestore indexes composite create \
  --collection-group=feedback \
  --query-scope=COLLECTION \
  --field-config=field-path=conversation_id,order=ASCENDING
```

#### Option C: Firebase CLI (Most Automated)

If you have Firebase CLI installed:

```bash
# Install Firebase CLI (if needed)
npm install -g firebase-tools

# Login to Firebase
firebase login

# Deploy indexes from firestore.indexes.json
firebase deploy --only firestore:indexes
```

**Monitor index creation:**

Indexes take 10-15 minutes to build. Check status:

```bash
gcloud firestore indexes composite list
```

Or view in [Firestore Console > Indexes](https://console.firebase.google.com/project/meded-gcp-sandbox/firestore/indexes)

### 3. Create Cloud Storage Bucket (for logs)

```bash
gsutil mb -p meded-gcp-sandbox -c STANDARD -l us-central1 gs://meded-feedback-bot-logs/
```

### 4. Set Up OAuth Credentials

1. Go to [Google Cloud Console > APIs & Services > Credentials](https://console.cloud.google.com/apis/credentials)
2. Create OAuth 2.0 Client ID (Web application type)
3. Add authorized redirect URIs:
   - For testing: `https://YOUR-SERVICE-URL/auth/callback`
   - For production: `https://YOUR-DOMAIN/auth/callback`
4. Note the Client ID and Client Secret - you'll need these for the next step

### 5. Configure Secrets in Secret Manager

**IMPORTANT:** Secrets (OAuth credentials and JWT secret) are now managed via Google Cloud Secret Manager for better security.

Run the automated setup script:

```bash
./setup_secrets.sh
```

This script will:
- Create secrets in Google Cloud Secret Manager
- Auto-generate a secure JWT secret key
- Prompt you for your OAuth Client ID and Client Secret (from step 4)
- Grant necessary IAM permissions to Cloud Run service account
- Verify the setup

**Optional:** Import from existing `.env.deployed` file if you have one.

The script creates these secrets:
- `preceptor-bot-jwt-secret` - Auto-generated secure random key
- `preceptor-bot-oauth-client-id` - Your OAuth Client ID
- `preceptor-bot-oauth-client-secret` - Your OAuth Client Secret

**Note:** The script is idempotent - safe to run multiple times. Existing secrets won't be overwritten.

## Deployment Methods

### Option 1: Quick Deploy (Recommended for First Time)

```bash
./deploy.sh
```

This uses Cloud Run's source-based deployment (builds from Dockerfile automatically).

### Option 2: Cloud Build (Production)

```bash
gcloud builds submit --config cloudbuild.yaml
```

This builds the container and deploys to Cloud Run in one step.

### Option 3: Manual Docker Build

```bash
# Build
docker build -t gcr.io/meded-gcp-sandbox/preceptor-feedback-bot:latest .

# Push
docker push gcr.io/meded-gcp-sandbox/preceptor-feedback-bot:latest

# Deploy
gcloud run deploy preceptor-feedback-bot \
  --image gcr.io/meded-gcp-sandbox/preceptor-feedback-bot:latest \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --timeout 600
```

## Environment Variables

### Secrets (Managed via Secret Manager)

Secrets are automatically injected from Google Cloud Secret Manager when you deploy using `./deploy.sh` or `cloudbuild.yaml`. **No manual configuration needed** after running `./setup_secrets.sh`.

The deployment scripts automatically configure:
- `JWT_SECRET_KEY` → from `preceptor-bot-jwt-secret`
- `OAUTH_CLIENT_ID` → from `preceptor-bot-oauth-client-id`
- `OAUTH_CLIENT_SECRET` → from `preceptor-bot-oauth-client-secret`

**To update a secret:**
```bash
echo -n 'NEW_SECRET_VALUE' | gcloud secrets versions add preceptor-bot-jwt-secret --data-file=-
```

Then redeploy to pick up the new value.

### OAuth Redirect URI

After first deployment, update `OAUTH_REDIRECT_URI` in your OAuth client settings:

1. Get your Cloud Run URL from deployment output
2. Add this to authorized redirect URIs: `https://YOUR-SERVICE-URL/auth/callback`
3. Go to [Google Cloud Console > APIs & Services > Credentials](https://console.cloud.google.com/apis/credentials)
4. Edit your OAuth 2.0 Client ID and add the redirect URI

### Non-Sensitive Variables

These are set automatically by `cloudbuild.yaml` but can be overridden:

```bash
DEPLOYMENT_ENV=cloud
GCP_PROJECT_ID=meded-gcp-sandbox
GCP_REGION=us-central1
MODEL_NAME=gemini-2.5-flash
LOG_BUCKET=meded-feedback-bot-logs
CLOUD_RUN_TIMEOUT=600
OAUTH_DOMAIN_RESTRICTION=true
OAUTH_ALLOWED_DOMAINS=case.edu
FIRESTORE_DATABASE=(default)
```

## Service Account Permissions

The `./setup_secrets.sh` script automatically grants Secret Manager permissions. For other permissions, ensure your Cloud Run service account has these roles:

```bash
# Get service account email
SERVICE_ACCOUNT=$(gcloud run services describe preceptor-feedback-bot \
  --region us-central1 \
  --format='value(spec.template.spec.serviceAccountName)')

# Grant necessary permissions
gcloud projects add-iam-policy-binding meded-gcp-sandbox \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/datastore.user"

gcloud projects add-iam-policy-binding meded-gcp-sandbox \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/aiplatform.user"

gsutil iam ch serviceAccount:${SERVICE_ACCOUNT}:objectCreator \
  gs://meded-feedback-bot-logs
```

**Note:** `setup_secrets.sh` already granted `roles/secretmanager.secretAccessor` for each secret.

## Post-Deployment Checklist

- [ ] Service is deployed and accessible
- [ ] OAuth login works with allowed domains
- [ ] Can create new conversation
- [ ] AI conversation works (no rate limit errors)
- [ ] Feedback generation works
- [ ] Feedback refinement works
- [ ] Dashboard loads past conversations
- [ ] Survey appears after finishing a session
- [ ] Survey submission and skip both work
- [ ] Firestore indexes are active (not building)
- [ ] Logs are being written to Cloud Storage

## Monitoring

### View Logs

```bash
gcloud run services logs tail preceptor-feedback-bot --region us-central1
```

### Check Service Status

```bash
gcloud run services describe preceptor-feedback-bot --region us-central1
```

### Monitor Firestore Usage

Go to Cloud Console > Firestore > Usage tab

## Troubleshooting

### "Index not ready" errors

Wait for Firestore indexes to finish building (can take 10-15 minutes). Check status:

```bash
gcloud firestore indexes composite list
```

Or create the missing index by clicking the error link, or using the manual commands in the setup section.

### OAuth redirect mismatch

Ensure `OAUTH_REDIRECT_URI` in Cloud Run matches the authorized redirect URI in OAuth client settings exactly.

### Rate limit (RESOURCE_EXHAUSTED) errors

- Verify `GCP_REGION` is set to specific region (us-central1), not "global"
- Check you're using stable model (gemini-2.5-flash), not experimental (-exp suffix)

### 500 errors on startup

Check that all required environment variables are set:

```bash
gcloud run services describe preceptor-feedback-bot \
  --region us-central1 \
  --format='value(spec.template.spec.containers[0].env)'
```

## Rollback

If deployment fails, rollback to previous revision:

```bash
gcloud run services update-traffic preceptor-feedback-bot \
  --to-revisions=PREVIOUS-REVISION-NAME=100 \
  --region us-central1
```

## Local Development

For local development, copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
# Edit .env with your local settings
```

Then run:

```bash
pip install -r requirements.txt
./start-dev.sh
```

Access at: http://localhost:8080
