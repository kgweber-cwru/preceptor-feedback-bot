#!/bin/bash
set -e

echo "🚀 Deploying Preceptor Feedback Bot to Cloud Run..."
echo ""
echo "📝 Note: Using secrets from Google Cloud Secret Manager"
echo "   If secrets are not set up, run: ./setup_secrets.sh"
echo ""

gcloud run deploy preceptor-feedback-bot \
  --source . \
  --region us-central1 \
  --project meded-gcp-sandbox \
  --timeout 600 \
  --set-env-vars="DEPLOYMENT_ENV=cloud,GCP_PROJECT_ID=meded-gcp-sandbox,GCP_REGION=us-central1,MODEL_NAME=gemini-2.5-flash,LOG_BUCKET=meded-feedback-bot-logs,CLOUD_RUN_TIMEOUT=600,OAUTH_DOMAIN_RESTRICTION=true,OAUTH_ALLOWED_DOMAINS=case.edu,FIRESTORE_DATABASE=(default),DEBUG=false,OAUTH_REDIRECT_URI=https://preceptor-feedback-bot-hki4fdufla-uc.a.run.app/auth/callback" \
  --set-secrets="JWT_SECRET_KEY=preceptor-bot-jwt-secret:latest,OAUTH_CLIENT_ID=preceptor-bot-oauth-client-id:latest,OAUTH_CLIENT_SECRET=preceptor-bot-oauth-client-secret:latest" \
  --allow-unauthenticated

echo ""
echo "✅ Deployment complete!"
echo "🌐 View your app at the URL above"