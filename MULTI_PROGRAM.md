# Multi-Program Support — Scope and Progress

## Overview

Extend the Preceptor Feedback Bot to support multiple training programs from a single codebase,
deployed as separate Cloud Run instances with per-program configuration. Initial target: MD Program
(existing) and MS in Anesthesia (MSA) Program.

Each program gets its own Cloud Run service, system prompt, branding, and rating scale. No behavior
changes to the existing MD deployment.

## Out of Scope

- Multi-institution OAuth (CCF, UH, MetroHealth, VA) — separate workstream, hand off to internal dev
- Per-program analytics or reporting dashboard
- MSA-specific survey questions (extend Phase 6 when requirements are confirmed)

---

## Phase 1 — Config Layer

Add new env vars to `app/config.py`:

| Var | Purpose | Examples |
|---|---|---|
| `PROGRAM_ID` | Machine identifier; used for Firestore field and template selection | `md`, `msa` |
| `PROGRAM_NAME` | Human-readable name for UI | `MD Program`, `MS in Anesthesia Program` |
| `PROGRAM_COLOR` | Primary accent color for CSS theming | `#0a3161`, `#2e7d5e` |
| `RATING_TYPE` | How the bot asks for ratings and how we parse them | `text`, `numeric` |

`SYSTEM_PROMPT_PATH` already exists — no change needed.

### Tasks
- [x] Add `PROGRAM_ID`, `PROGRAM_NAME`, `PROGRAM_COLOR`, `RATING_TYPE` to `Settings` in `app/config.py`
- [x] Add defaults that preserve current MD behavior (`PROGRAM_ID=md`, etc.)
- [x] Update `.env.example` with new vars and comments

### Notes
2026-03-26 — Complete. All four vars added to `Settings` with MD-safe defaults. `RATING_TYPE`
validated on startup (`text` or `numeric`; ValueError otherwise). `get_deployment_info()` now
includes program fields. All 77 existing tests pass.

---

## Phase 2 — Firestore Data Model

Add `program` field to conversation, feedback, and survey Firestore documents.
Add `rating` field to feedback documents (structured extracted value).

### Tasks
- [x] Add `program: str` to `app/models/conversation.py`
- [x] Add `program: str` and `rating: Optional[str | int]` to `app/models/feedback.py`
- [x] Add `program: str` to `app/models/survey.py`
- [x] Update `app/services/firestore_service.py` write methods to populate `program` from `settings.PROGRAM_ID`
- [x] Update `app/services/firestore_service.py` to write `rating` field on feedback documents

### Notes
2026-03-26 — Complete. All three models updated with `program` (default `"md"` for backward
compat with existing Firestore documents). `Feedback` also gets `rating: Optional[str | int]`.
`create_feedback()` signature updated to accept `rating`; mock in `tests/conftest.py` updated
to match. All 77 tests pass.

---

## Phase 3 — Rating Extraction

The system prompt (per-program) instructs the AI to elicit a rating during conversation. At feedback
generation time, extract the rating from the generated text and store it as a structured value.

**Fragility note:** Extraction relies on the system prompt producing a consistently formatted rating
line (e.g., `Overall Rating: 4/5` or `Overall Rating: Meets Expectations`). Validate this during
MSA system prompt development.

### Tasks
- [x] Add extraction logic in `vertex_ai_client.py::generate_feedback()` — regex pass after generation
- [x] Handle graceful failure (rating not found → `None`, no crash)
- [x] Pass extracted rating through to `ConversationService` and into Firestore write
- [ ] Validate extraction with both `numeric` and `text` rating formats — covered in Phase 8 tests

### Notes
2026-03-27 — Complete. Added `_extract_rating()` to `VertexAIClient`: searches for the
`**Clinical Performance**: ...` bullet; returns `int` for `RATING_TYPE=numeric` (parses leading
digit), `str` for `RATING_TYPE=text`, `None` on any miss or error. `generate_feedback()` now
returns `(content, rating)` tuple. `ConversationService` unpacks it and passes `rating` to
`firestore.create_feedback()`. Three test mocks updated to return tuples. All 77 tests pass.

---

## Phase 4 — Branding

Inject program name and accent color into templates. MD keeps existing styling; MSA gets a
distinct but CWRU-appropriate accent.

### Tasks
- [x] Add CSS custom properties (`--program-accent`, `--program-accent-dark`) to `app/templates/base.html`
- [x] Inject `PROGRAM_NAME` and `PROGRAM_COLOR` into Jinja2 template context (global or per-route)
- [x] Display `PROGRAM_NAME` in header and page title
- [x] Display `PROGRAM_NAME` on login page
- [x] Confirm MSA accent color — settled on `#1565a0` (medium steel blue, distinct from MD navy `#0a3161`)

### Notes
2026-03-27 — Complete. `program_name`, `program_color`, `program_id` added as Jinja2 globals in
`dependencies.py`. `base.html` injects `--program-accent` and `--program-accent-dark` as CSS
custom properties on `:root`; nav brand and loading spinner use `var(--program-accent)` via
inline style. Program name appears as a small sub-label beneath the app name in the nav and as
a coloured line on the login page. Page `<title>` includes program name. All 77 tests pass.

---

## Phase 5 — Feedback Detection Generalization

`_contains_formal_feedback()` checks for MD-specific section headers. If MSA uses the same output
format, this may be a no-op.

**Blocked on:** MSA system prompt.

### Tasks
- [ ] Review MSA system prompt output format once available
- [ ] If headers differ: add `FEEDBACK_MARKERS` env var (comma-separated); fall back to MD defaults if unset
- [ ] If headers are the same: close this phase with no code changes

### Notes
<!-- progress notes go here -->

---

## Phase 6 — Survey Parameterization

Make the survey template selectable per-program without building a full config-driven system.

### Tasks
- [ ] ~~Rename current survey template to `survey_default.html`~~ — skipped, not needed
- [x] Add `SURVEY_TEMPLATE` config var that selects which template to render
- [x] Update `app/api/survey.py` to use `settings.SURVEY_TEMPLATE`
- [ ] When MSA survey requirements land: add `survey_msa.html` and point config at it

### Notes
2026-03-30 — Complete (for now). Both programs use `survey.html` via `SURVEY_TEMPLATE=survey.html`.
`show_survey()` now renders `settings.SURVEY_TEMPLATE` instead of a hardcoded string. Adding an
MSA-specific template later requires only a new file + env var change, no route changes.

---

## Phase 7 — Deployment Infrastructure

### Tasks
- [x] Create `deploy-md.sh`
- [x] Create `deploy-msa.sh`
- [x] Create `.env.msa.example`
- [x] Create `setup_secrets_msa.sh` (grants MSA service account access to shared secrets)
- [x] Distinct Cloud Run service names: `preceptor-feedback-bot`, `preceptor-feedback-msa`
- [ ] Update `CLAUDE.md` to document two-service deployment — deferred until after first MSA deploy
- [ ] Update `REDIRECT_URI` in `deploy-msa.sh` after first MSA Cloud Run deploy

### Notes
2026-03-30 — Complete. `deploy-md.sh` and `deploy-msa.sh` are standalone scripts with all
program-specific env vars inlined. Secrets are shared between programs; `setup_secrets_msa.sh`
handles the IAM grant for the MSA service account. `deploy.sh` left unchanged for backward compat.
**Action needed after first MSA deploy:** copy the real Cloud Run URL into `REDIRECT_URI` in
`deploy-msa.sh` and add it to the OAuth client in Google Cloud Console.

---

## Phase 8 — Tests

### Tasks
- [x] Update `tests/conftest.py` mock fixtures to include `program` and `rating` fields
- [x] Add tests for rating extraction: valid numeric, valid text, missing/malformed input
- [x] Confirm all existing MD tests pass unchanged

### Notes
2026-03-27 — Complete. Added four new test files (105 new tests, 182 total):
- `test_vertex_ai_client.py` — `_extract_rating` (text/numeric/edge cases),
  `_contains_formal_feedback`, `_fix_markdown_formatting`, `should_conclude_conversation`
- `test_markdown.py` — `markdown_to_html` and `_fix_definition_lists` (full coverage)
- `test_utils.py` — `timeago` and `format_datetime` (full coverage)
- `test_firestore_service.py` — write/read operations with mocked Firestore client;
  verifies `program` and `rating` fields are persisted correctly
Overall coverage: 62% → 74% (threshold 70% now passing).

2026-03-30 — Added `tests/test_multi_program.py` (28 tests covering config validation,
prompt file existence, SURVEY_TEMPLATE wiring, dev quick-test routes, and program/rating
field persistence on all Firestore models). Also cleaned up archive/ and deploy.sh.
Two config tests fixed to be environment-independent (invariant checks rather than
exact-default assertions, since .env may be set to either program). Final: 210 passed, 75%.

---

## Sequencing

```
Phase 1 (Config)  ──►  Phase 4 (Branding)        } No MSA prompt needed;
                  ──►  Phase 6 (Survey shell)     } can start immediately
                  ──►  Phase 7 (Deploy scripts)   }

Phase 2 (Firestore)  ──►  Phase 3 (Rating)        } Can start immediately
                     ──►  Phase 8 (Tests)          }

Phase 5 (Feedback markers)  ──►  BLOCKED on MSA system prompt
                                 (likely a no-op)

MSA prompt arrives  ──►  Integrate + smoke test MSA instance locally
                    ──►  Deploy MSA Cloud Run service
```

---

## Decisions Log

| Date | Decision | Rationale |
|---|---|---|
| 2026-03-26 | Single repo, two Cloud Run instances | Shared bug fixes; easy to add future programs |
| 2026-03-26 | `program` field in Firestore (not separate collections) | Data governance handled outside the app |
| 2026-03-26 | Rating elicited conversationally by AI, then extracted | Keeps UI simple; fragility mitigated by prompt design |
| 2026-03-26 | Survey parameterized by template name, not config-driven schema | YAGNI — MSA survey requirements not yet known |
| 2026-03-26 | Multi-institution OAuth deferred | Complexity warrants separate workstream and dev handoff |
| 2026-03-26 | Phase 5 (feedback markers) blocked on MSA prompt | May be zero effort if output format is the same |
