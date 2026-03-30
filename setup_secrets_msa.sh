#!/bin/bash
# Grant a service account access to the shared secrets for the MSA deployment.
#
# In the standard setup, the MSA Cloud Run service reuses the existing SA
# (preceptor-feedback-bot@meded-gcp-sandbox.iam.gserviceaccount.com), which already
# has Secret Manager access from the original setup_secrets.sh run.
# In that case, you do NOT need to run this script.
#
# Only run this if you are using a different/new service account for MSA.
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
  echo -e "${RED}Error: No GCP project configured.${NC}"
  echo "Run: gcloud config set project YOUR_PROJECT_ID"
  exit 1
fi

# Change this to the SA you want to grant access to
MSA_SA="preceptor-feedback-bot@${PROJECT_ID}.iam.gserviceaccount.com"

echo -e "${YELLOW}Note: This script is only needed if the MSA service uses a different SA than MD.${NC}"
echo -e "${YELLOW}The standard setup reuses ${MSA_SA} — which already has access.${NC}"
echo ""
read -p "Continue granting access for ${MSA_SA}? (y/n): " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
  echo "Aborted."
  exit 0
fi

SECRET_NAMES=(
  "preceptor-bot-jwt-secret"
  "preceptor-bot-oauth-client-id"
  "preceptor-bot-oauth-client-secret"
)

for SECRET in "${SECRET_NAMES[@]}"; do
  echo -e "${BLUE}Granting ${MSA_SA} access to ${SECRET}...${NC}"
  gcloud secrets add-iam-policy-binding "$SECRET" \
    --project="$PROJECT_ID" \
    --member="serviceAccount:${MSA_SA}" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet &>/dev/null
  echo -e "${GREEN}Done: ${SECRET}${NC}"
done

echo ""
echo -e "${GREEN}Service account granted access to all shared secrets.${NC}"
