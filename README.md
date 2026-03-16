# Preceptor Feedback Bot

A conversational AI tool that helps medical school faculty provide structured, competency-based feedback on medical students after clinical encounters. Built with FastAPI, Google Vertex AI (Gemini models), Google Cloud Firestore, and Google OAuth.

## Overview

This application guides preceptors through a brief (3-5 minute) conversation to gather observations about a student's clinical performance. It then generates two structured outputs:

1. **Structured Summary** - Organized by strengths, areas for improvement, and developmental suggestions
2. **Student-Facing Narrative** - Constructive, supportive feedback framed as opportunities for growth

All feedback is organized according to [CWRU School of Medicine's core competencies](https://case.edu/medicine/curriculum/curriculum-overview/competencies-and-education-program-objectives):
- Professionalism
- Teamwork and Interprofessonal Collaboration
- Reflective Practice
- Interpersonal and Communication Skills
- Knowledge for Practice
- Patient Care
- Systems-based Practice

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  FastAPI + HTMX UI (app/)                                   │
│  ├─ Authentication (Google OAuth 2.0 + JWT)                 │
│  ├─ API Routes (auth, conversations, feedback, survey, user) │
│  └─ Services                                                │
│      ├─ VertexAIClient → Google Vertex AI (Gemini)          │
│      ├─ ConversationService                                 │
│      ├─ FirestoreService → Google Cloud Firestore           │
│      └─ OAuthSessionStore → Google Cloud Firestore          │
└─────────────────────────────────────────────────────────────┘
         │
         ├─> Firestore: Conversations, Feedback, Users, Surveys
         ├─> Secret Manager: OAuth & JWT secrets
         └─> Cloud Storage: Logs & archives
```

## Prerequisites

- **Python 3.12+** (tested with 3.12 and 3.13)
- **Google Cloud Platform account** with:
  - Vertex AI API enabled
  - Firestore enabled
  - Secret Manager API enabled
  - Cloud Storage enabled
  - Service account with appropriate roles
- **Google OAuth 2.0 Credentials** (for authentication)

## Quick Start

### 1. Clone and Install

```bash
git clone <repository-url>
cd preceptor-feedback-bot
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Local Development

```bash
cp .env.example .env
# Edit .env with your settings (see below)
```

### 3. Run Locally

```bash
./start-dev.sh
```

This script activates the virtual environment, validates your `.env`, and starts the server with auto-reload.
Access at: http://localhost:8080

Alternatively, run directly:
```bash
uvicorn app.main:app --reload --port 8080
```

## Full Deployment Guide

For complete deployment instructions including GCP setup, OAuth configuration, Firestore indexes, and Secret Manager, see **[DEPLOYMENT.md](DEPLOYMENT.md)**.

## Project Structure

```
preceptor-feedback-bot/
├── app/                              # Main application
│   ├── main.py                      # FastAPI app entry point
│   ├── config.py                    # Configuration management
│   ├── dependencies.py              # FastAPI dependencies
│   ├── middleware/
│   │   └── auth_middleware.py       # JWT authentication
│   ├── api/                         # API route handlers
│   │   ├── auth.py                  # OAuth login/logout
│   │   ├── conversations.py         # Conversation management
│   │   ├── feedback.py              # Feedback generation
│   │   ├── survey.py                # Post-session survey
│   │   ├── user.py                  # Dashboard & user profile
│   │   └── dev.py                   # Dev-only: quick-test endpoint (DEBUG mode)
│   ├── services/                    # Business logic
│   │   ├── auth_service.py          # OAuth & JWT handling
│   │   ├── firestore_service.py     # Database operations
│   │   ├── conversation_service.py  # Conversation orchestration
│   │   ├── oauth_session_store.py   # Firestore-backed OAuth state
│   │   └── vertex_ai_client.py      # Vertex AI wrapper
│   ├── models/                      # Pydantic data models
│   │   ├── user.py
│   │   ├── conversation.py
│   │   ├── feedback.py
│   │   └── survey.py
│   ├── templates/                   # Jinja2 HTML templates
│   │   ├── base.html
│   │   ├── login.html
│   │   ├── dashboard.html
│   │   ├── conversation.html
│   │   ├── feedback.html
│   │   ├── survey.html
│   │   └── components/
│   ├── static/                      # CSS, JS, images
│   └── utils/                       # Utilities
│       ├── markdown.py              # Markdown→HTML renderer (handles headings, bullets, definition-list fix)
│       └── time_formatting.py
├── prompts/
│   └── system_prompt.md            # AI system instructions
├── tests/                           # Test suite
├── archive/                         # Historical files and migration docs
├── .env.example                     # Environment variable template
├── requirements.txt                 # Python dependencies
├── pytest.ini                       # Test configuration
├── Dockerfile                       # Container definition
├── start-dev.sh                     # Local development startup script
├── deploy.sh                        # Quick deployment script
├── setup_secrets.sh                 # Secret Manager setup
├── cloudbuild.yaml                  # Cloud Build configuration
├── firestore.indexes.json           # Firestore index definitions
├── firestore.rules                  # Firestore security rules
├── DEPLOYMENT.md                    # Complete deployment guide
└── CLAUDE.md                        # Architecture & development guide
```

## Local Development Configuration

### Required Environment Variables

Create a `.env` file with these values:

```bash
# Deployment
DEPLOYMENT_ENV=local

# GCP Configuration
GCP_PROJECT_ID=your-gcp-project-id
GCP_REGION=us-central1
GCP_CREDENTIALS_PATH=./path-to-service-account-key.json

# Model Configuration
MODEL_NAME=gemini-2.5-flash
TEMPERATURE=0.7
MAX_OUTPUT_TOKENS=2048

# Conversation Settings
MAX_TURNS=10

# Local Logging
LOG_TO_FILE=true
LOG_DIRECTORY=./logs
LOG_LEVEL=INFO

# Firestore
FIRESTORE_DATABASE=(default)

# OAuth (get from Google Cloud Console)
OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
OAUTH_CLIENT_SECRET=your-client-secret
OAUTH_REDIRECT_URI=http://localhost:8080/auth/callback
OAUTH_DOMAIN_RESTRICTION=false  # Set to true for production

# JWT (generate with: python -c "import secrets; print(secrets.token_urlsafe(32))")
JWT_SECRET_KEY=your-secure-random-key
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=168

# Debug
DEBUG=true
```

## Cloud Deployment

### Option 1: Quick Deploy (Recommended)

```bash
# First time: Set up secrets in Secret Manager
./setup_secrets.sh

# Deploy to Cloud Run
./deploy.sh
```

### Option 2: Cloud Build CI/CD

```bash
gcloud builds submit --config cloudbuild.yaml
```

### Environment Variables (Cloud Run)

Non-sensitive variables are set in `deploy.sh`:
- `DEPLOYMENT_ENV=cloud`
- `GCP_PROJECT_ID`, `GCP_REGION`
- `MODEL_NAME`, `LOG_BUCKET`
- `OAUTH_DOMAIN_RESTRICTION=true`
- `OAUTH_ALLOWED_DOMAINS=case.edu`

Sensitive variables are managed via **Secret Manager**:
- `JWT_SECRET_KEY` → `preceptor-bot-jwt-secret`
- `OAUTH_CLIENT_ID` → `preceptor-bot-oauth-client-id`
- `OAUTH_CLIENT_SECRET` → `preceptor-bot-oauth-client-secret`

## Key Features

### Authentication & Security
- **Google OAuth 2.0** with PKCE for secure login
- **Domain restriction** - Limit access to specific email domains (e.g., case.edu)
- **JWT sessions** - Secure, httpOnly cookies
- **Firestore security rules** - Users can only access their own data
- **Secret Manager** - Centralized secret management

### Conversation Management
- **Real-time chat** with HTMX for smooth UX (no page refreshes)
- **Student name tracking** - Required before starting, preserved throughout
- **Turn counter** - Tracks conversation progress
- **Premature feedback detection** - Prevents AI from generating feedback too early
- **Firestore persistence** - All conversations saved to database

### Feedback Generation
- **Structured output** - Structured summary + student narrative
- **Refinement support** - Users can request changes to generated feedback
- **Version history** - Firestore stores all refinement iterations
- **Download as text** - Export final feedback

### Dashboard
- **Conversation history** - View all past conversations
- **Search & filter** - Find conversations by student name, status, date
- **Status tracking** - Active, completed, archived conversations

## Configuration Options

### Available Models

Edit `MODEL_NAME` in `.env`:

```bash
# Recommended (stable, latest)
MODEL_NAME=gemini-2.5-flash

# Alternative options
MODEL_NAME=gemini-1.5-pro
MODEL_NAME=gemini-1.5-flash
```

### Conversation Parameters

```bash
TEMPERATURE=0.7              # 0.0 (deterministic) to 1.0 (creative)
MAX_OUTPUT_TOKENS=2048       # Max response length
MAX_TURNS=10                 # Max conversation exchanges
MIN_COMPETENCY_COVERAGE=3    # Min competencies to cover
```

## Troubleshooting

### "Invalid state parameter" during OAuth
- Clear browser cookies for the site
- Verify `OAUTH_REDIRECT_URI` matches your Cloud Run URL exactly
- Check that redirect URI is added to OAuth client in Google Cloud Console

### Firestore "Missing index" errors
- Wait 10-15 minutes for indexes to build after deployment
- Or click the provided link in the error to create the index
- Deploy indexes with: `firebase deploy --only firestore:indexes`

### Rate limit (RESOURCE_EXHAUSTED) errors
- Verify `GCP_REGION` is set to specific region (e.g., `us-central1`), NOT "global"
- Use stable models (e.g., `gemini-2.5-flash`), NOT experimental (`-exp` suffix)

### OAuth redirect mismatch
- Ensure `OAUTH_REDIRECT_URI` in Cloud Run matches authorized redirect URIs in OAuth client
- Format: `https://your-service-url/auth/callback`

## Development Guidelines

### Editing AI Behavior

To modify conversation style, questions, or output format, edit `prompts/system_prompt.md`. **Do NOT remove** the instruction about waiting to generate feedback - this prevents premature feedback generation.

### Testing Locally

```bash
# Run the test suite
pytest

# Run with coverage report
pytest --cov=app

# Run specific test file
pytest tests/test_survey.py -v
```

### Dev Quick-Test (skip inventing conversations)

When `DEBUG=true`, an amber **⚡ Quick Test** button appears on the dashboard. It creates a pre-seeded conversation covering multiple competencies and drops you straight onto the feedback generation page — useful for iterating on feedback formatting without running through a full conversation each time.

```bash
# Run development server with auto-reload
./start-dev.sh

# Or directly:
uvicorn app.main:app --reload --port 8080 --log-level debug

# Access at http://localhost:8080
# API docs at http://localhost:8080/docs
```

### Firestore Local Emulator (Optional)

```bash
# Install Firebase CLI
npm install -g firebase-tools

# Start Firestore emulator
firebase emulators:start --only firestore

# Update .env
FIRESTORE_EMULATOR_HOST=localhost:8080
```

## Security & Privacy

- **FERPA Compliance**: All feedback treated as protected educational records
- **No PHI**: Users reminded not to include patient identifiers
- **Domain restriction**: Optional - limit to specific email domains
- **Firestore security rules**: Enforced at database level
- **Secrets management**: Never commit credentials - use Secret Manager
- **Audit logging**: All conversations logged for quality improvement

## Support & Contribution

For questions about CWRU medical education workflows, contact your medical education IT team.

### Making Changes

1. Test locally: `uvicorn app.main:app --reload --port 8080`
2. Check linting: `ruff check app/`
3. Update documentation if changing deployment procedures
4. Deploy: `./deploy.sh`
5. Verify in production

## License

Internal use only - Case Western Reserve University School of Medicine
