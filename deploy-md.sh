#!/bin/bash
# Deploy the MD Program instance of the Preceptor Feedback Bot to Cloud Run.
# Secrets must be set up first: ./setup_secrets.sh
set -e

SERVICE_NAME="preceptor-feedback-md"
PROJECT="meded-gcp-sandbox"
REGION="us-central1"
REDIRECT_URI="https://preceptor-feedback-md-hki4fdufla-uc.a.run.app/auth/callback"
LOG_BUCKET="meded-feedback-bot-logs"

echo "Deploying MD Program instance: ${SERVICE_NAME}"

gcloud run deploy "${SERVICE_NAME}" \
  --source . \
  --region "${REGION}" \
  --project "${PROJECT}" \
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
PROGRAM_ID=md,\
PROGRAM_NAME=University MD Program,\
PROGRAM_COLOR=#0a3161,\
RATING_TYPE=text,\
SYSTEM_PROMPT_PATH=./prompts/system_prompt_md.md,\
SURVEY_TEMPLATE=survey.html" \
  --set-secrets="\
JWT_SECRET_KEY=preceptor-bot-jwt-secret:latest,\
OAUTH_CLIENT_ID=preceptor-bot-oauth-client-id:latest,\
OAUTH_CLIENT_SECRET=preceptor-bot-oauth-client-secret:latest" \
  --allow-unauthenticated

echo ""
echo "MD deployment complete."
echo "Update REDIRECT_URI in this script if the service URL has changed."
