# Firestore Setup Guide

## Step 1: Enable Firestore in Google Cloud Console

1. **Go to Firestore in GCP Console**
   - Visit: https://console.cloud.google.com/firestore
   - Select your project: `meded-gcp-sandbox`

2. **Create Firestore Database**
   - Click "Create Database" (if not already created)
   - Choose **Native Mode** (not Datastore mode)
   - Select location: **nam5 (United States)** or your preferred multi-region
   - Click "Create Database"

3. **Wait for Database Creation**
   - This takes about 1-2 minutes
   - You'll see a message when it's ready

## Step 2: Deploy Security Rules

We've already created security rules in `firestore.rules`. Now deploy them:

### Option A: Using Firebase CLI (Recommended)

```bash
# Install Firebase CLI (if not already installed)
npm install -g firebase-tools

# Login to Firebase
firebase login

# Initialize Firebase in your project
firebase init firestore

# When prompted:
# - Select your GCP project (meded-gcp-sandbox)
# - Use existing firestore.rules file (y)
# - Use firestore.indexes.json (press Enter for default)

# Deploy the rules
firebase deploy --only firestore:rules
```

### Option B: Using GCP Console

1. Go to: https://console.cloud.google.com/firestore/rules
2. Copy the contents of `firestore.rules` file
3. Paste into the editor
4. Click "Publish"

## Step 3: Verify Security Rules

The security rules ensure:
- Users can only read/write their own data
- Each collection is protected by user_id
- No unauthorized access possible

**Rules Summary:**
```javascript
// Users can only access their own profile
match /users/{userId} {
  allow read, write: if isOwner(userId);
}

// Users can only access their own conversations
match /conversations/{conversationId} {
  allow read, write: if resource.data.user_id == request.auth.uid;
}

// Users can only access their own feedback
match /feedback/{feedbackId} {
  allow read, write: if resource.data.user_id == request.auth.uid;
}
```

## Step 4: Create Firestore Indexes (Optional but Recommended)

For better query performance, create these indexes:

1. Go to: https://console.cloud.google.com/firestore/indexes

2. **Create Index for Conversations:**
   - Collection: `conversations`
   - Fields:
     - `user_id` (Ascending)
     - `updated_at` (Descending)
   - Query scope: Collection

3. **Create Index for Feedback:**
   - Collection: `feedback`
   - Fields:
     - `user_id` (Ascending)
     - `generated_at` (Descending)
   - Query scope: Collection

**Note:** Firestore will auto-create indexes when you run queries. If you see an error with an index creation URL, just click it and create the suggested index.

## Step 5: Test Firestore Connection Locally

```bash
# Make sure your service account has Firestore permissions
# The service account needs:
# - Cloud Datastore User (or Firestore User)
# - Service Account Token Creator

# Test the connection
source .venv/bin/activate
python3 << 'EOF'
from google.cloud import firestore
import os

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./meded-gcp-sandbox-90054d0b3d2d.json"

try:
    db = firestore.Client(project="meded-gcp-sandbox", database="(default)")
    print("✓ Firestore connection successful!")

    # Test write
    test_ref = db.collection('_test').document('connection_test')
    test_ref.set({'timestamp': firestore.SERVER_TIMESTAMP, 'test': True})
    print("✓ Write test successful!")

    # Test read
    doc = test_ref.get()
    if doc.exists:
        print("✓ Read test successful!")

    # Cleanup
    test_ref.delete()
    print("✓ Firestore is ready to use!")

except Exception as e:
    print(f"✗ Error: {e}")
    print("\nTroubleshooting:")
    print("1. Check that Firestore is enabled in GCP Console")
    print("2. Verify service account has 'Cloud Datastore User' role")
    print("3. Check GCP_CREDENTIALS_PATH in .env")
EOF
```

## Step 6: Update Service Account Permissions

Your service account needs Firestore access:

1. Go to: https://console.cloud.google.com/iam-admin/iam
2. Find your service account
3. Click "Edit" (pencil icon)
4. Add role: **Cloud Datastore User**
5. Click "Save"

## Step 7: Start the Application

```bash
# Start the development server
./start-dev.sh

# Or manually:
source .venv/bin/activate
export DEBUG=true
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

## Step 8: Test in Browser

1. **Open browser:** http://localhost:8080
2. **Login with Google** (OAuth flow)
3. **Dashboard:** You should see "Start New Conversation" form
4. **Enter student name** (e.g., "Test Student")
5. **Click "Start Feedback Session"**
6. **You should be redirected** to the conversation page
7. **See initial AI greeting** acknowledging the student name
8. **Type a response** and send
9. **Watch AI respond** in real-time (HTMX magic!)

## Troubleshooting

### Error: "7 PERMISSION_DENIED: Missing or insufficient permissions"

**Solution:** Add "Cloud Datastore User" role to your service account
```bash
# Get your service account email
gcloud iam service-accounts list

# Grant role
gcloud projects add-iam-policy-binding meded-gcp-sandbox \
  --member="serviceAccount:YOUR-SERVICE-ACCOUNT@meded-gcp-sandbox.iam.gserviceaccount.com" \
  --role="roles/datastore.user"
```

### Error: "Collection does not exist"

**Solution:** Collections are created automatically on first write. This is normal.

### Error: "Index not found"

**Solution:** Click the URL in the error message to create the required index in GCP Console.

### Error: "Chat session not initialized"

**Solution:** Check that:
1. Vertex AI is enabled: https://console.cloud.google.com/apis/library/aiplatform.googleapis.com
2. Service account has "Vertex AI User" role
3. Model name in .env is correct (gemini-2.5-flash or gemini-2.5-flash)

## Firestore Collections Created

Once you start using the app, these collections will be created:

### users
- Stores user profiles from OAuth
- Fields: email, name, domain, picture_url, created_at, last_login

### conversations
- Stores conversation history
- Fields: user_id, student_name, status, messages[], metadata, timestamps

### feedback
- Stores generated feedback
- Fields: conversation_id, user_id, student_name, versions[], current_version

## Viewing Data in Console

To see your data:
1. Go to: https://console.cloud.google.com/firestore/data
2. Select collection (users, conversations, or feedback)
3. Browse documents
4. View/edit data directly

## Next Steps

After Firestore is working:
- Test full conversation flow
- Generate feedback (Phase 3)
- View conversation history (Phase 4)
- Deploy to Cloud Run (Phase 6)
