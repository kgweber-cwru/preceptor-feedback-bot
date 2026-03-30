# Preceptor Feedback Bot

A conversational AI tool that helps medical school faculty provide structured, competency-based feedback on students after clinical encounters. Built with FastAPI, Google Vertex AI (Gemini models), Google Cloud Firestore, and Google OAuth.

Supports multiple training programs from a single codebase, each deployed as a separate Cloud Run service. Current programs: **MD Program** and **MS in Anesthesia (MSA) Program**.

## Overview

The application guides preceptors through a brief (3–5 minute) conversation to gather observations about a student's clinical performance. It then generates two structured outputs:

1. **Structured Summary** — Organized by strengths, areas for improvement, and developmental suggestions
2. **Student-Facing Narrative** — Constructive, supportive feedback framed as opportunities for growth

Each program uses its own competency framework and rating scale. The MD program uses a qualitative scale (meets/exceeds expectations); the MSA program uses a 1–5 numeric scale. Feedback is organized according to the relevant program's competencies.

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
         ├─> Secret Manager: OAuth & JWT secrets (shared between programs)
         └─> Cloud Storage: Logs
```

## Prerequisites

- **Python 3.12+** (tested with 3.12 and 3.13)
- **Google Cloud Platform account** with:
  - Vertex AI API enabled
  - Firestore enabled
  - Secret Manager API enabled
  - Cloud Storage enabled
  - Service account with appropriate roles
- **Google OAuth 2.0 Credentials**

## Quick Start

### 1. Clone and Install

```bash
git clone <repository-url>
cd preceptor-feedback-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Local Development

```bash
# For MD program:
cp .env.example .env

# For MSA program:
cp .env.msa.example .env

# Edit .env with your GCP credentials and OAuth settings
```

### 3. Run Locally

```bash
./start-dev.sh
# Access at: http://localhost:8080
```

## Project Structure

```
preceptor-feedback-bot/
├── app/
│   ├── main.py                      # FastAPI entry point
│   ├── config.py                    # Settings (program config, model, OAuth, etc.)
│   ├── api/
│   │   ├── auth.py                  # OAuth login/logout
│   │   ├── conversations.py         # Conversation management
│   │   ├── feedback.py              # Feedback generation & refinement
│   │   ├── survey.py                # Post-session survey
│   │   ├── user.py                  # Dashboard & user profile
│   │   └── dev.py                   # Dev-only: quick-test endpoints
│   ├── services/
│   │   ├── vertex_ai_client.py      # Vertex AI wrapper + rating extraction
│   │   ├── conversation_service.py  # Conversation orchestration
│   │   ├── firestore_service.py     # All Firestore CRUD
│   │   ├── auth_service.py          # OAuth & JWT handling
│   │   └── oauth_session_store.py   # Firestore-backed OAuth state
│   ├── models/                      # Pydantic models (user, conversation, feedback, survey)
│   ├── templates/                   # Jinja2 HTML templates
│   └── utils/
│       ├── markdown.py              # Markdown→HTML renderer
│       └── time_formatting.py
├── prompts/
│   ├── system_prompt_md.md          # MD program system prompt
│   └── system_prompt_msa.md         # MSA program system prompt
├── tests/                           # Test suite (pytest, 70% coverage threshold)
├── .env.example                     # MD program env template
├── .env.msa.example                 # MSA program env template
├── deploy.sh                        # Deploy MD program (preceptor-feedback-bot)
├── deploy-msa.sh                    # Deploy MSA program (preceptor-feedback-msa)
├── setup_secrets.sh                 # One-time Secret Manager setup
├── firestore.indexes.json
├── firestore.rules
├── DEPLOYMENT.md                    # Full deployment guide
└── CLAUDE.md                        # Architecture & development guide
```

## Program Configuration

Each Cloud Run deployment targets one program via environment variables:

| Variable | MD | MSA |
|---|---|---|
| `PROGRAM_ID` | `md` | `msa` |
| `PROGRAM_NAME` | `University MD Program` | `MS in Anesthesia Program` |
| `PROGRAM_COLOR` | `#0a3161` (navy) | `#1565a0` (steel blue) |
| `RATING_TYPE` | `text` | `numeric` |
| `SYSTEM_PROMPT_PATH` | `./prompts/system_prompt_md.md` | `./prompts/system_prompt_msa.md` |
| `SURVEY_TEMPLATE` | `survey.html` | `survey.html` |

## Cloud Deployment

### First-time setup (run once per project)

```bash
./setup_secrets.sh
```

### Deploy MD program

```bash
./deploy.sh
```

### Deploy MSA program

```bash
./deploy-msa.sh
# After first deploy: update REDIRECT_URI in deploy-msa.sh with the real Cloud Run URL,
# add it to the OAuth client in Google Cloud Console, then redeploy.
```

Both services use the same service account (`preceptor-feedback-bot@...`) and share the same Secret Manager secrets.

## Key Configuration Variables

```bash
# Required
GCP_PROJECT_ID=your-project-id
GCP_REGION=us-central1          # Never "global" — causes rate limit issues
GCP_CREDENTIALS_PATH=./key.json # Local dev only

# Model
MODEL_NAME=gemini-2.5-flash     # Use stable versions, not -exp suffix

# OAuth
OAUTH_CLIENT_ID=...
OAUTH_CLIENT_SECRET=...
OAUTH_REDIRECT_URI=http://localhost:8080/auth/callback
OAUTH_DOMAIN_RESTRICTION=false  # Set to true + OAUTH_ALLOWED_DOMAINS to restrict by domain

# Program (per-deployment)
PROGRAM_ID=md
PROGRAM_NAME=University MD Program
PROGRAM_COLOR=#0a3161
RATING_TYPE=text
SYSTEM_PROMPT_PATH=./prompts/system_prompt_md.md
```

## Dev Quick-Test Feature

When `DEBUG=true`, the dashboard shows two amber **⚡ Quick Test** buttons that bypass the conversation phase and drop you directly onto the feedback generation page.

- **Quick Test — MD**: outpatient primary care, text rating ("Exceeds expectations")
- **Quick Test — MSA**: emergent OR case, numeric rating (4/5)

## Troubleshooting

**"Invalid state parameter" during OAuth**
- Clear browser cookies, verify `OAUTH_REDIRECT_URI` matches your service URL exactly

**Firestore "Missing index" errors**
- Wait 10–15 minutes after deployment, or run: `firebase deploy --only firestore:indexes`

**Rate limit (RESOURCE_EXHAUSTED) errors**
- Verify `GCP_REGION` is a specific region (`us-central1`), never `global`
- Use stable model versions (`gemini-2.5-flash`), never `-exp` suffix

## Testing

```bash
pytest                  # all tests
pytest --cov=app        # with coverage (threshold: 70%)
pytest -m unit          # unit tests only
```

## License

Internal use only — Case Western Reserve University School of Medicine
