#!/bin/bash
# Development server startup script for FastAPI Preceptor Feedback Bot

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Preceptor Feedback Bot (FastAPI)${NC}"
echo ""

# Check if .venv exists
if [ ! -d ".venv" ]; then
    echo -e "${RED}Error: Virtual environment not found${NC}"
    echo "Run: python3 -m venv .venv"
    exit 1
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source .venv/bin/activate

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Warning: .env file not found${NC}"
    echo "Creating from .env.example..."
    cp .env.example .env
    echo -e "${RED}Please update .env with your OAuth credentials${NC}"
    echo "See OAUTH_SETUP.md for instructions"
fi

# Check for OAuth credentials
if ! grep -q "OAUTH_CLIENT_ID=.*apps.googleusercontent.com" .env; then
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}⚠️  OAuth credentials not configured${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "To enable Google OAuth login:"
    echo "1. Create OAuth credentials in Google Cloud Console"
    echo "2. Add to .env file:"
    echo "   OAUTH_CLIENT_ID=your-id.apps.googleusercontent.com"
    echo "   OAUTH_CLIENT_SECRET=your-secret"
    echo ""
    echo "See OAUTH_SETUP.md for detailed instructions"
    echo ""
    echo -e "${YELLOW}Starting server WITHOUT OAuth (health checks only)${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
fi

# Set debug mode
export DEBUG=true

# Start server
echo -e "${GREEN}Starting FastAPI server on http://localhost:8080${NC}"
echo ""
echo "Available endpoints:"
echo "  • http://localhost:8080/          - Login page"
echo "  • http://localhost:8080/health    - Health check"
echo "  • http://localhost:8080/docs      - API documentation"
echo "  • http://localhost:8080/config    - Config info"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""

python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
