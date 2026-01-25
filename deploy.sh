#!/bin/bash
# AI Governance Platform - Cloud Run Deployment Script

set -e  # Exit on error

# ===========================================
# Configuration
# ===========================================
PROJECT_ID="${PROJECT_ID:-ai-governance-demo-2025}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-ai-governance-platform}"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}AI Governance Platform - Cloud Run Deploy${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""

# ===========================================
# Pre-flight checks
# ===========================================
echo -e "${YELLOW}Checking prerequisites...${NC}"

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Error: gcloud CLI is not installed${NC}"
    echo "Install from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    echo "Install from: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if user is logged in
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -n1 > /dev/null 2>&1; then
    echo -e "${RED}Error: Not logged in to gcloud${NC}"
    echo "Run: gcloud auth login"
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites met${NC}"
echo ""

# ===========================================
# Set project
# ===========================================
echo -e "${YELLOW}Setting GCP project to: ${PROJECT_ID}${NC}"
gcloud config set project ${PROJECT_ID}

# ===========================================
# Enable required APIs
# ===========================================
echo -e "${YELLOW}Enabling required GCP APIs...${NC}"
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    containerregistry.googleapis.com \
    bigquery.googleapis.com \
    secretmanager.googleapis.com \
    --quiet

echo -e "${GREEN}✓ APIs enabled${NC}"
echo ""

# ===========================================
# Build and push Docker image
# ===========================================
echo -e "${YELLOW}Building Docker image...${NC}"

# Option 1: Build locally and push (faster for development)
# docker build -t ${IMAGE_NAME}:latest .
# docker push ${IMAGE_NAME}:latest

# Option 2: Build using Cloud Build (recommended for CI/CD)
gcloud builds submit --tag ${IMAGE_NAME}:latest .

echo -e "${GREEN}✓ Image built and pushed${NC}"
echo ""

# ===========================================
# Check for required secrets
# ===========================================
echo -e "${YELLOW}Checking secrets in Secret Manager...${NC}"

# Check if GEMINI_API_KEY secret exists
if ! gcloud secrets describe gemini-api-key --project=${PROJECT_ID} > /dev/null 2>&1; then
    echo -e "${YELLOW}Creating GEMINI_API_KEY secret...${NC}"
    echo -e "${RED}Please enter your Gemini API key:${NC}"
    read -s GEMINI_KEY
    echo -n "${GEMINI_KEY}" | gcloud secrets create gemini-api-key --data-file=- --project=${PROJECT_ID}
    echo -e "${GREEN}✓ Secret created${NC}"
else
    echo -e "${GREEN}✓ GEMINI_API_KEY secret exists${NC}"
fi

echo ""

# ===========================================
# Deploy to Cloud Run
# ===========================================
echo -e "${YELLOW}Deploying to Cloud Run...${NC}"

gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME}:latest \
    --region ${REGION} \
    --platform managed \
    --allow-unauthenticated \
    --memory 1Gi \
    --cpu 1 \
    --min-instances 0 \
    --max-instances 10 \
    --port 8080 \
    --set-env-vars "PROJECT_ID=${PROJECT_ID},LOCATION=${REGION},BIGQUERY_DATASET=ai_governance,DEBUG=false,GEMINI_MODEL=gemini-2.0-flash" \
    --set-secrets "GEMINI_API_KEY=gemini-api-key:latest" \
    --timeout 300

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""

# Get the service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format 'value(status.url)')
echo -e "Service URL: ${GREEN}${SERVICE_URL}${NC}"
echo ""
echo "Endpoints:"
echo "  - API Docs:    ${SERVICE_URL}/docs"
echo "  - Health:      ${SERVICE_URL}/health"
echo "  - Demo Chat:   ${SERVICE_URL}/api/v1/demo/chat-ui"
echo "  - Dashboard:   ${SERVICE_URL}/dashboard"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Test the API: curl ${SERVICE_URL}/health"
echo "2. Open demo chat: ${SERVICE_URL}/api/v1/demo/chat-ui"
echo "3. View logs: gcloud run logs read ${SERVICE_NAME} --region ${REGION}"