# Archive Directory

This directory contains historical files from the Streamlit-to-FastAPI migration process.

## Directory Structure

### `streamlit-version/`
Contains the original Streamlit implementation files:
- `app.py` - Original Streamlit application
- `config.py` - Original configuration (replaced by `app/config.py`)
- `utils/` - Original utilities (replaced by `app/services/`)
- Test files for Streamlit version

**Note**: These files are kept for reference only. The current production app uses the FastAPI implementation in the `app/` directory.

### `migration-docs/`
Contains intermediate documentation created during the migration:
- `PHASE4_IMPLEMENTATION_SUMMARY.md` - Dashboard implementation notes
- `SESSION_SUMMARY.md` - Migration session notes
- `FIRESTORE_SETUP.md` - Firestore configuration notes (consolidated into DEPLOYMENT.md)
- `OAUTH_SETUP.md` - OAuth setup notes (consolidated into DEPLOYMENT.md)

**Note**: This information has been consolidated into the main documentation files (DEPLOYMENT.md, CLAUDE.md, README.md).

## Migration Timeline

- **Pre-Migration**: Streamlit-based app with local file storage
- **Migration Start**: December 2025
- **Migration Complete**: December 2025 (Phases 1-4 complete)
- **Current**: FastAPI + HTMX + Firestore + Google OAuth

## Current Production Implementation

The production application uses:
- **Framework**: FastAPI + HTMX
- **Database**: Google Cloud Firestore
- **Authentication**: Google OAuth 2.0 with domain restriction
- **AI**: Google Vertex AI (Gemini models)
- **Secrets**: Google Secret Manager
- **Hosting**: Google Cloud Run

For current documentation, see:
- `../README.md` - Overview and quick start
- `../DEPLOYMENT.md` - Complete deployment guide
- `../CLAUDE.md` - Architecture and development guide
- `../MIGRATION_TODO.md` - Migration progress tracker
