#!/bin/bash
# Deploy the MSA Program instance of the Preceptor Feedback Bot to Cloud Run.
# Prereq: ./setup_secrets.sh must have been run once for the project.
# The MSA service reuses the same service account as the MD service — no separate SA setup needed.
set -e

SERVICE_NAME="preceptor-feedback-msa"
PROJECT="meded-gcp-sandbox"
REGION="us-central1"
SERVICE_ACCOUNT="preceptor-feedback-bot@meded-gcp-sandbox.iam.gserviceaccount.com"
# TODO: Replace with actual MSA Cloud Run URL after first deploy
REDIRECT_URI="https://preceptor-feedback-msa-hki4fdufla-uc.a.run.app/auth/callback"
LOG_BUCKET="meded-feedback-bot-logs"

echo "Deploying MSA Program instance: ${SERVICE_NAME}"

gcloud run deploy "${SERVICE_NAME}" \
  --source . \
  --region "${REGION}" \
  --project "${PROJECT}" \
  --service-account "${SERVICE_ACCOUNT}" \
  --labels app=preceptor-feedback-bot \
  --timeout 600 \
  --set-env-vars="\
DEPLOYMENT_ENV=cloud,\
GCP_PROJECT_ID=${PROJECT},\
GCP_REGION=${REGION},\
MODEL_NAME=gemini-2.5-flash,\
LOG_BUCKET=${LOG_BUCKET},\
CLOUD_RUN_TIMEOUT=600,\
OAUTH_DOMAIN_RESTRICTION=true,\
OAUTH_ALLOWED_DOMAINS=case.edu,\
FIRESTORE_DATABASE=(default),\
DEBUG=false,\
OAUTH_REDIRECT_URI=${REDIRECT_URI},\
PROGRAM_ID=msa,\
PROGRAM_NAME=MS in Anesthesia Program,\
PROGRAM_COLOR=#1565a0,\
RATING_TYPE=numeric,\
SYSTEM_PROMPT_PATH=./prompts/system_prompt_msa.md,\
SURVEY_TEMPLATE=survey.html" \
  --set-secrets="\
JWT_SECRET_KEY=preceptor-bot-jwt-secret:latest,\
OAUTH_CLIENT_ID=preceptor-bot-oauth-client-id:latest,\
OAUTH_CLIENT_SECRET=preceptor-bot-oauth-client-secret:latest" \
  --allow-unauthenticated

echo ""
echo "MSA deployment complete."
echo "IMPORTANT: After first deploy, copy the service URL and update REDIRECT_URI in this script."
echo "Also add the new redirect URI to the OAuth client in Google Cloud Console."
