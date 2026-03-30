#!/bin/bash
# Grant the MSA Cloud Run service account access to the shared secrets.
# Run this AFTER setup_secrets.sh has created the secrets for the first time.
# The secrets themselves are shared between MD and MSA instances.
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
  echo -e "${RED}Error: No GCP project configured.${NC}"
  echo "Run: gcloud config set project YOUR_PROJECT_ID"
  exit 1
fi

SERVICE_NAME="preceptor-feedback-msa"

echo -e "${BLUE}Looking up service account for ${SERVICE_NAME}...${NC}"

# After first deploy, Cloud Run uses the default compute service account.
# If you've assigned a custom SA to the MSA service, update this line.
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
MSA_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo -e "${GREEN}Service account: ${MSA_SA}${NC}"
echo ""

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
echo -e "${GREEN}MSA service account granted access to all shared secrets.${NC}"
echo "Next: ./deploy-msa.sh"
