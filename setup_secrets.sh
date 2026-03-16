#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Secret Manager Setup for Preceptor Bot${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Get GCP project ID
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
  echo -e "${RED}Error: No GCP project configured.${NC}"
  echo "Run: gcloud config set project YOUR_PROJECT_ID"
  exit 1
fi

echo -e "${GREEN}✓ Using GCP project: ${PROJECT_ID}${NC}"
echo ""

# Get project number for service account
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
CLOUD_RUN_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo -e "${GREEN}✓ Cloud Run service account: ${CLOUD_RUN_SA}${NC}"
echo ""

# Secret names
JWT_SECRET_NAME="preceptor-bot-jwt-secret"
OAUTH_CLIENT_ID_NAME="preceptor-bot-oauth-client-id"
OAUTH_CLIENT_SECRET_NAME="preceptor-bot-oauth-client-secret"

# Function to check if secret exists
secret_exists() {
  gcloud secrets describe "$1" --project="$PROJECT_ID" &>/dev/null
  return $?
}

# Function to create secret
create_secret() {
  local secret_name=$1
  local secret_value=$2

  if secret_exists "$secret_name"; then
    echo -e "${YELLOW}⚠ Secret ${secret_name} already exists. Skipping creation.${NC}"
    echo -e "  To update, run: echo -n 'NEW_VALUE' | gcloud secrets versions add ${secret_name} --data-file=-"
  else
    echo -e "${BLUE}Creating secret: ${secret_name}${NC}"
    echo -n "$secret_value" | gcloud secrets create "$secret_name" \
      --project="$PROJECT_ID" \
      --replication-policy="automatic" \
      --data-file=-
    echo -e "${GREEN}✓ Created secret: ${secret_name}${NC}"
  fi
}

# Function to grant IAM permissions
grant_access() {
  local secret_name=$1

  echo -e "${BLUE}Granting access to ${CLOUD_RUN_SA} for ${secret_name}${NC}"
  gcloud secrets add-iam-policy-binding "$secret_name" \
    --project="$PROJECT_ID" \
    --member="serviceAccount:${CLOUD_RUN_SA}" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet &>/dev/null
  echo -e "${GREEN}✓ Granted access for: ${secret_name}${NC}"
}

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Step 1: JWT Secret${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Generate JWT secret
if secret_exists "$JWT_SECRET_NAME"; then
  echo -e "${YELLOW}⚠ JWT secret already exists. Using existing secret.${NC}"
  JWT_SECRET=""
else
  echo "Generating secure random JWT secret..."
  JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
  echo -e "${GREEN}✓ Generated JWT secret${NC}"
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Step 2: OAuth Credentials${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "You need to provide your Google OAuth credentials."
echo "Get these from: https://console.cloud.google.com/apis/credentials"
echo ""

# Check if .env.deployed exists
if [ -f ".env.deployed" ]; then
  echo -e "${YELLOW}Found .env.deployed file. Would you like to import secrets from it?${NC}"
  read -p "Import from .env.deployed? (y/n): " import_choice
  if [[ "$import_choice" =~ ^[Yy]$ ]]; then
    source .env.deployed
    OAUTH_CLIENT_ID="$OAUTH_CLIENT_ID"
    OAUTH_CLIENT_SECRET="$OAUTH_CLIENT_SECRET"
    echo -e "${GREEN}✓ Imported OAuth credentials from .env.deployed${NC}"
  fi
fi

# Prompt for OAuth Client ID if not imported
if [ -z "$OAUTH_CLIENT_ID" ]; then
  read -p "Enter OAuth Client ID: " OAUTH_CLIENT_ID
fi

# Prompt for OAuth Client Secret if not imported
if [ -z "$OAUTH_CLIENT_SECRET" ]; then
  read -sp "Enter OAuth Client Secret (hidden): " OAUTH_CLIENT_SECRET
  echo ""
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Step 3: Creating Secrets${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Create secrets (only if they don't exist)
if [ -n "$JWT_SECRET" ]; then
  create_secret "$JWT_SECRET_NAME" "$JWT_SECRET"
fi
create_secret "$OAUTH_CLIENT_ID_NAME" "$OAUTH_CLIENT_ID"
create_secret "$OAUTH_CLIENT_SECRET_NAME" "$OAUTH_CLIENT_SECRET"

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Step 4: Granting IAM Permissions${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Grant access to all secrets
grant_access "$JWT_SECRET_NAME"
grant_access "$OAUTH_CLIENT_ID_NAME"
grant_access "$OAUTH_CLIENT_SECRET_NAME"

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}  Setup Complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Summary of configured secrets:"
echo "  • ${JWT_SECRET_NAME}"
echo "  • ${OAUTH_CLIENT_ID_NAME}"
echo "  • ${OAUTH_CLIENT_SECRET_NAME}"
echo ""
echo "IAM permissions granted to:"
echo "  • ${CLOUD_RUN_SA}"
echo ""
echo -e "${GREEN}Next steps:${NC}"
echo "  1. Update deploy.sh and cloudbuild.yaml to use --set-secrets"
echo "  2. Delete JWT_service_key file"
echo "  3. Add .env.deployed to .gitignore"
echo "  4. Deploy with: ./deploy.sh"
echo ""
echo -e "${YELLOW}Note: It may take 1-2 minutes for IAM permissions to fully propagate.${NC}"
echo ""
