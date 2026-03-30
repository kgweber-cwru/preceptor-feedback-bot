"""
Unit tests for FirestoreService.

Uses a patched Firestore client — no real GCP connection required.
Focuses on verifying that write methods persist the correct fields
(including the new `program` and `rating` fields) and that read methods
handle missing documents gracefully.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch, AsyncMock

from app.models.survey import SurveyCreate, HelpfulnessRating, LikelihoodRating
from app.config import settings


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    """A MagicMock standing in for google.cloud.firestore.Client."""
    db = MagicMock()

    # Default doc_ref returned by .add() — callers access [1].id
    mock_doc_ref = MagicMock()
    mock_doc_ref.id = "generated_doc_id"
    db.collection.return_value.add.return_value = (MagicMock(), mock_doc_ref)

    # Default document().get() — does not exist
    mock_doc = MagicMock()
    mock_doc.exists = False
    db.collection.return_value.document.return_value.get.return_value = mock_doc

    # Default query — empty result set
    db.collection.return_value.where.return_value.limit.return_value.stream.return_value = []
    db.collection.return_value.where.return_value.order_by.return_value.limit.return_value.stream.return_value = []

    return db


@pytest.fixture
def firestore_svc(mock_db):
    """FirestoreService with the real Firestore client replaced by mock_db."""
    with patch("app.services.firestore_service.firestore.Client", return_value=mock_db):
        from app.services.firestore_service import FirestoreService
        svc = FirestoreService()
        # Directly replace db so tests can assert on it
        svc.db = mock_db
        return svc, mock_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _last_add_arg(mock_db):
    """Return the dict that was passed to the most recent .add() call."""
    return mock_db.collection.return_value.add.call_args[0][0]


# ---------------------------------------------------------------------------
# create_conversation
# ---------------------------------------------------------------------------

class TestCreateConversation:

    @pytest.mark.asyncio
    async def test_returns_conversation_with_id(self, firestore_svc):
        svc, _ = firestore_svc
        conv = await svc.create_conversation("user_1", "Sarah Chen", "gemini-2.5-flash")
        assert conv.conversation_id == "generated_doc_id"
        assert conv.student_name == "Sarah Chen"

    @pytest.mark.asyncio
    async def test_writes_program_field(self, firestore_svc):
        svc, mock_db = firestore_svc
        await svc.create_conversation("user_1", "Sarah Chen", "gemini-2.5-flash")
        saved = _last_add_arg(mock_db)
        assert saved["program"] == settings.PROGRAM_ID

    @pytest.mark.asyncio
    async def test_writes_status_active(self, firestore_svc):
        svc, mock_db = firestore_svc
        await svc.create_conversation("user_1", "Sarah Chen", "gemini-2.5-flash")
        saved = _last_add_arg(mock_db)
        assert saved["status"] == "active"

    @pytest.mark.asyncio
    async def test_writes_model_in_metadata(self, firestore_svc):
        svc, mock_db = firestore_svc
        await svc.create_conversation("user_1", "Sarah Chen", "gemini-2.5-flash")
        saved = _last_add_arg(mock_db)
        assert saved["metadata"]["model"] == "gemini-2.5-flash"


# ---------------------------------------------------------------------------
# create_feedback
# ---------------------------------------------------------------------------

class TestCreateFeedback:

    @pytest.mark.asyncio
    async def test_returns_feedback_with_id(self, firestore_svc):
        svc, _ = firestore_svc
        fb = await svc.create_feedback("conv_1", "user_1", "Sarah Chen", "Good feedback")
        assert fb.feedback_id == "generated_doc_id"
        assert fb.student_name == "Sarah Chen"

    @pytest.mark.asyncio
    async def test_writes_program_field(self, firestore_svc):
        svc, mock_db = firestore_svc
        await svc.create_feedback("conv_1", "user_1", "Sarah Chen", "Good feedback")
        saved = _last_add_arg(mock_db)
        assert saved["program"] == settings.PROGRAM_ID

    @pytest.mark.asyncio
    async def test_writes_rating_when_provided(self, firestore_svc):
        svc, mock_db = firestore_svc
        await svc.create_feedback(
            "conv_1", "user_1", "Sarah Chen", "Good feedback",
            rating="Meets Expectations"
        )
        saved = _last_add_arg(mock_db)
        assert saved["rating"] == "Meets Expectations"

    @pytest.mark.asyncio
    async def test_writes_numeric_rating(self, firestore_svc):
        svc, mock_db = firestore_svc
        await svc.create_feedback("conv_1", "user_1", "Sarah Chen", "Good feedback", rating=4)
        saved = _last_add_arg(mock_db)
        assert saved["rating"] == 4

    @pytest.mark.asyncio
    async def test_writes_none_rating_when_omitted(self, firestore_svc):
        svc, mock_db = firestore_svc
        await svc.create_feedback("conv_1", "user_1", "Sarah Chen", "Good feedback")
        saved = _last_add_arg(mock_db)
        assert saved["rating"] is None

    @pytest.mark.asyncio
    async def test_initial_version_is_stored(self, firestore_svc):
        svc, mock_db = firestore_svc
        await svc.create_feedback("conv_1", "user_1", "Sarah Chen", "Initial content")
        saved = _last_add_arg(mock_db)
        assert len(saved["versions"]) == 1
        assert saved["versions"][0]["type"] == "initial"
        assert saved["versions"][0]["content"] == "Initial content"

    @pytest.mark.asyncio
    async def test_updates_conversation_has_feedback_flag(self, firestore_svc):
        svc, mock_db = firestore_svc
        await svc.create_feedback("conv_1", "user_1", "Sarah Chen", "Good feedback")
        # The conversation document should be updated
        mock_db.collection.return_value.document.return_value.update.assert_called()
        update_call = mock_db.collection.return_value.document.return_value.update.call_args[0][0]
        assert update_call.get("has_feedback") is True


# ---------------------------------------------------------------------------
# create_survey
# ---------------------------------------------------------------------------

class TestCreateSurvey:

    @pytest.mark.asyncio
    async def test_returns_survey_with_id(self, firestore_svc):
        svc, _ = firestore_svc
        survey_data = SurveyCreate()
        survey = await svc.create_survey("conv_1", "user_1", "Sarah Chen", survey_data)
        assert survey.survey_id == "generated_doc_id"

    @pytest.mark.asyncio
    async def test_writes_program_field(self, firestore_svc):
        svc, mock_db = firestore_svc
        survey_data = SurveyCreate()
        await svc.create_survey("conv_1", "user_1", "Sarah Chen", survey_data)
        saved = _last_add_arg(mock_db)
        assert saved["program"] == settings.PROGRAM_ID

    @pytest.mark.asyncio
    async def test_writes_skipped_flag(self, firestore_svc):
        svc, mock_db = firestore_svc
        survey_data = SurveyCreate()
        await svc.create_survey("conv_1", "user_1", "Sarah Chen", survey_data, skipped=True)
        saved = _last_add_arg(mock_db)
        assert saved["skipped"] is True

    @pytest.mark.asyncio
    async def test_writes_ratings(self, firestore_svc):
        svc, mock_db = firestore_svc
        survey_data = SurveyCreate(
            helpfulness_rating=HelpfulnessRating.VERY_HELPFUL,
            likelihood_rating=LikelihoodRating.LIKELY,
        )
        await svc.create_survey("conv_1", "user_1", "Sarah Chen", survey_data)
        saved = _last_add_arg(mock_db)
        assert saved["helpfulness_rating"] == "Very helpful"
        assert saved["likelihood_rating"] == "Likely"


# ---------------------------------------------------------------------------
# create_user
# ---------------------------------------------------------------------------

class TestCreateUser:

    @pytest.mark.asyncio
    async def test_returns_user_with_id(self, firestore_svc):
        svc, _ = firestore_svc
        from app.models.user import UserCreate
        user_data = UserCreate(
            email="test@case.edu", name="Test User",
            domain="case.edu", picture_url=None
        )
        user = await svc.create_user(user_data)
        assert user.user_id == "generated_doc_id"
        assert user.email == "test@case.edu"

    @pytest.mark.asyncio
    async def test_writes_correct_fields(self, firestore_svc):
        svc, mock_db = firestore_svc
        from app.models.user import UserCreate
        user_data = UserCreate(
            email="test@case.edu", name="Test User",
            domain="case.edu", picture_url=None
        )
        await svc.create_user(user_data)
        saved = _last_add_arg(mock_db)
        assert saved["email"] == "test@case.edu"
        assert saved["name"] == "Test User"
        assert saved["domain"] == "case.edu"


# ---------------------------------------------------------------------------
# get_conversation
# ---------------------------------------------------------------------------

class TestGetConversation:

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, firestore_svc):
        svc, mock_db = firestore_svc
        mock_db.collection.return_value.document.return_value.get.return_value.exists = False
        result = await svc.get_conversation("nonexistent_id")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_conversation_when_found(self, firestore_svc):
        svc, mock_db = firestore_svc
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.id = "conv_abc"
        mock_doc.to_dict.return_value = {
            "user_id": "user_1",
            "student_name": "Sarah Chen",
            "program": "md",
            "status": "active",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "metadata": {
                "model": "gemini-2.5-flash",
                "total_turns": 2,
                "project_id": "test-project",
                "environment": "local",
            },
            "messages": [],
            "has_feedback": False,
        }
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        result = await svc.get_conversation("conv_abc")
        assert result is not None
        assert result.student_name == "Sarah Chen"
        assert result.program == "md"


# ---------------------------------------------------------------------------
# get_feedback_by_conversation
# ---------------------------------------------------------------------------

class TestGetFeedbackByConversation:

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, firestore_svc):
        svc, mock_db = firestore_svc
        mock_db.collection.return_value.where.return_value.limit.return_value.stream.return_value = []
        result = await svc.get_feedback_by_conversation("conv_xyz")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_feedback_when_found(self, firestore_svc):
        svc, mock_db = firestore_svc
        mock_doc = MagicMock()
        mock_doc.id = "fb_123"
        mock_doc.to_dict.return_value = {
            "conversation_id": "conv_xyz",
            "user_id": "user_1",
            "student_name": "Sarah Chen",
            "program": "md",
            "rating": "Meets Expectations",
            "generated_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "versions": [
                {
                    "version": 1,
                    "timestamp": datetime.utcnow(),
                    "type": "initial",
                    "content": "Good feedback",
                    "request": None,
                }
            ],
            "current_version": 1,
        }
        mock_db.collection.return_value.where.return_value.limit.return_value.stream.return_value = [mock_doc]
        result = await svc.get_feedback_by_conversation("conv_xyz")
        assert result is not None
        assert result.rating == "Meets Expectations"
        assert result.program == "md"


# ---------------------------------------------------------------------------
# get_user_by_email
# ---------------------------------------------------------------------------

class TestGetUserByEmail:

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, firestore_svc):
        svc, mock_db = firestore_svc
        mock_db.collection.return_value.where.return_value.limit.return_value.stream.return_value = []
        result = await svc.get_user_by_email("nobody@case.edu")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_user_when_found(self, firestore_svc):
        svc, mock_db = firestore_svc
        mock_doc = MagicMock()
        mock_doc.id = "user_abc"
        mock_doc.to_dict.return_value = {
            "email": "someone@case.edu",
            "name": "Someone",
            "domain": "case.edu",
            "picture_url": None,
            "created_at": datetime.utcnow(),
            "last_login": datetime.utcnow(),
        }
        mock_db.collection.return_value.where.return_value.limit.return_value.stream.return_value = [mock_doc]
        result = await svc.get_user_by_email("someone@case.edu")
        assert result is not None
        assert result.email == "someone@case.edu"


# ---------------------------------------------------------------------------
# get_survey_by_conversation
# ---------------------------------------------------------------------------

class TestGetSurveyByConversation:

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, firestore_svc):
        svc, mock_db = firestore_svc
        mock_db.collection.return_value.where.return_value.limit.return_value.stream.return_value = []
        result = await svc.get_survey_by_conversation("conv_xyz")
        assert result is None
