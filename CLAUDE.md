# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A conversational AI tool that helps medical school faculty provide structured, competency-based feedback on medical students after clinical encounters. Built with FastAPI, HTMX, Google Vertex AI (Gemini), Google Cloud Firestore, and Google OAuth 2.0.

The application guides preceptors through a brief (3–5 minute) conversation, then generates two outputs organized by CWRU School of Medicine's core competencies:
1. **Clerkship Director Summary** — Structured bullets (strengths, areas for improvement, suggestions)
2. **Student-Facing Narrative** — Constructive, supportive feedback for the student

After completing a session, preceptors are prompted to fill out an optional post-session survey.

## Common Commands

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — at minimum set GCP_PROJECT_ID, GCP_REGION, GCP_CREDENTIALS_PATH,
# OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET, JWT_SECRET_KEY

# Run locally
./start-dev.sh
# or directly:
uvicorn app.main:app --reload --port 8080

# Run tests
pytest
pytest --cov=app          # with coverage
pytest tests/test_survey.py -v  # specific file
```

```bash
# Deploy to Cloud Run
./setup_secrets.sh  # one-time Secret Manager setup
./deploy.sh
```

## Architecture

### Core Components

**Entry Point:**
- `app/main.py` — FastAPI app initialization, middleware registration, route mounting, lifespan handler

**Configuration:**
- `app/config.py` — `Settings` class (pydantic_settings). Singleton exposed as `settings`. All model settings (`MODEL_NAME`, `TEMPERATURE`, `MAX_OUTPUT_TOKENS`), conversation parameters (`MAX_TURNS`), OAuth/JWT config, Firestore settings, and deployment flags are centralized here. Key method: `settings.get_model_display_name()`.

**Authentication:**
- `app/middleware/auth_middleware.py` — JWT validation from `httpOnly` cookies; injects current user into request state
- `app/api/auth.py` — OAuth 2.0 routes: `GET /auth/login`, `GET /auth/callback`, `POST /auth/logout`
- `app/services/auth_service.py` — PKCE flow, token exchange, JWT generation/validation, domain restriction
- `app/services/oauth_session_store.py` — Firestore-backed OAuth state store (avoids multi-instance Cloud Run issues with in-memory state)

**AI Integration:**
- `app/services/vertex_ai_client.py` — Wrapper around `google-genai` SDK. Key methods:
  - `start_conversation()` → initial greeting string
  - `send_message(user_message)` → `(response_text, contains_feedback)` tuple
  - `generate_feedback(student_name)` → structured feedback string
  - `refine_feedback(refinement_request)` → refined feedback string
  - `_contains_formal_feedback(text)` → detects premature feedback (see invariant below)
  - `_call_with_backoff(func, ...)` → exponential backoff for rate limits

**Business Logic:**
- `app/services/conversation_service.py` — Orchestrates `VertexAIClient` + `FirestoreService`; handles conversation creation, message persistence, turn tracking
- `app/services/firestore_service.py` — All Firestore CRUD: users, conversations, messages, feedback versions, surveys

**API Routes:**
- `app/api/conversations.py` — Create, list, get conversations; send messages (via HTMX)
- `app/api/feedback.py` — Generate feedback, refine feedback, finish session
- `app/api/survey.py` — Display, submit, and skip post-session survey
- `app/api/user.py` — Dashboard, user profile

**Data Models:**
- `app/models/user.py`, `conversation.py`, `feedback.py`, `survey.py` — Pydantic models for all Firestore documents

**Templates:**
- `app/templates/` — Jinja2 templates. `base.html` is the layout. HTMX is used for all dynamic interactions (no page reloads for chat or feedback generation).
- `app/templates/components/` — Reusable partials: `message.html`, `conversation_card.html`, `feedback_content.html`

**Prompting:**
- `prompts/system_prompt.md` — Canonical system instruction. Controls conversational style, probing behavior, competency framework, and the critical rule: **do NOT generate formal feedback during the conversation phase**.

### Critical Behavior Invariant: Premature Feedback Detection

The conversation phase must NOT produce final feedback until `generate_feedback()` is explicitly called.

- `app/services/vertex_ai_client.py::_contains_formal_feedback()` detects if the model ignores instructions and generates feedback early
- Checks for markers like `**Clerkship Director Summary`, `**Student-Facing Narrative`, `**Strengths**`, etc.
- `send_message()` returns `(response_text, contains_feedback)` — the API layer treats `contains_feedback=True` as a warning signal
- **If output format markers change, update `feedback_markers` in `_contains_formal_feedback()`**

### Conversation Workflow

1. User authenticates via Google OAuth
2. Dashboard: start new conversation by entering student name
3. `ConversationService.create_conversation()` → creates Firestore record + initializes `VertexAIClient` + fetches initial greeting
4. Preceptor and AI exchange messages (HTMX; max `MAX_TURNS`)
5. "Generate Feedback" → `ConversationService.generate_feedback()` → Firestore `feedback` subcollection
6. Optional: refine feedback with free-text input
7. "Finish" → marks conversation complete, redirects to survey
8. Survey: two required multiple-choice questions + optional open text + optional contact info; can be skipped entirely

### Firestore Data Model

Collections:
- `users/{user_id}` — email, name, domain, last login
- `conversations/{conversation_id}` — user_id, student_name, model, status, messages[], turn_count, timestamps
- `feedback/{feedback_id}` — conversation_id, user_id, content, versions[], is_final
- `surveys/{survey_id}` — conversation_id, user_id, student_name, helpfulness_rating, likelihood_rating, comments, contact_name, contact_email, skipped, submitted_at
- `oauth_sessions/{session_id}` — short-lived OAuth PKCE state

### Session / State Management

There is no in-process session state. All state is persisted in Firestore and retrieved per-request. JWT cookie identifies the user. Conversation state (messages, turn count, status) lives in the `conversations` collection.

### Credentials Handling

**Local:** Set `GCP_CREDENTIALS_PATH` in `.env` to a service account JSON file. `VertexAIClient` sets `GOOGLE_APPLICATION_CREDENTIALS` automatically.

**Cloud (Cloud Run):** Set `DEPLOYMENT_ENV=cloud`. Uses Application Default Credentials — no key file needed. Sensitive config (JWT secret, OAuth client ID/secret) is managed via **Secret Manager** (run `./setup_secrets.sh` once).

## Common Modification Patterns

### Change conversational behavior, questions, or tone
Edit `prompts/system_prompt.md`. Keep the "only gather information" instruction intact unless also updating the feedback detection logic.

### Switch model
Update `MODEL_NAME` in `.env` or Cloud Run environment variables. Add a display name mapping in `app/config.py::get_model_display_name()` if needed.

### Modify premature feedback detection
Update `feedback_markers` list in `app/services/vertex_ai_client.py::_contains_formal_feedback()`.

### Add a new survey question
1. `app/models/survey.py` — add enum or field to `SurveyBase`
2. `app/templates/survey.html` — add form element
3. `app/api/survey.py` — add `Form(...)` param to `submit_survey`, update `SurveyCreate(...)` call, pass new context to template if needed
4. `app/services/firestore_service.py` — add field to `survey_dict` in `create_survey()`
5. `tests/conftest.py` — update mock `create_survey()`
6. `tests/test_survey.py` and `tests/test_authorization.py` — update payloads and assertions

### Add a new API route
Add to `app/api/`, register the router in `app/main.py`.

### Add a new Firestore operation
Add method to `app/services/firestore_service.py`. Use `async def` and `FieldFilter` for queries.

### Modify UI flow
Edit the relevant Jinja2 template and its HTMX attributes. FastAPI route handlers return `TemplateResponse` for full pages or HTML fragments for HTMX partial updates.

## Testing

```bash
pytest                    # all tests
pytest --cov=app          # with coverage (configured in pytest.ini; threshold 70%)
pytest -m survey          # by marker
pytest tests/test_survey.py tests/test_authorization.py -v
```

Tests use a `MockFirestoreService` in `tests/conftest.py` — no real Firestore connection needed. GCP credentials are not required to run the test suite.

Markers: `integration`, `unit`, `auth`, `survey` (defined in `pytest.ini`).

## Safeguards and Privacy

- System prompt reminds preceptors not to include patient identifiers (PHI)
- All feedback treated as FERPA-protected educational records
- Firestore security rules enforce per-user data access at the database level
- `OAUTH_DOMAIN_RESTRICTION=true` + `OAUTH_ALLOWED_DOMAINS` limit logins to trusted email domains (e.g., `case.edu`)
- Service account JSON files are `.gitignore`d — never commit credentials

## Critical Configuration Requirements

### Avoiding RESOURCE_EXHAUSTED (429) Errors

- **MUST use a specific region** — e.g., `GCP_REGION=us-central1`. **Never `global`** — causes quota routing issues
- **Use stable model versions** — e.g., `gemini-2.5-flash`. Avoid `-exp` suffix models (2–10 RPM vs 60+ RPM)
- `_call_with_backoff()` retries up to 5× with exponential backoff + jitter (~2s → ~32s, max ~60s total)

### Example correct `.env`
```bash
GCP_REGION=us-central1          # NOT "global"
MODEL_NAME=gemini-2.5-flash     # NOT "gemini-2.0-flash-exp"
```

## Deployment Environments

**Local (`DEPLOYMENT_ENV=local`):**
- Reads `.env` file (python-dotenv)
- Requires `GCP_CREDENTIALS_PATH` pointing to service account JSON
- OAuth secrets in `.env`

**Cloud (`DEPLOYMENT_ENV=cloud`):**
- Environment variables set in Cloud Run service definition (`deploy.sh`)
- OAuth + JWT secrets injected from Secret Manager (configured by `setup_secrets.sh`)
- Uses Application Default Credentials (Cloud Run service account)
- `CLOUD_RUN_TIMEOUT` controls request timeout (default 600s)
- `LOG_BUCKET` enables Cloud Storage logging
