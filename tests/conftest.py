"""
Pytest configuration and shared fixtures for integration tests.
"""

import os
import sys
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from httpx import AsyncClient, ASGITransport

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set test environment before importing app
os.environ["DEPLOYMENT_ENV"] = "local"
os.environ["DEBUG"] = "true"
os.environ["GCP_PROJECT_ID"] = "test-project"
os.environ["GCP_REGION"] = "us-central1"
os.environ["MODEL_NAME"] = "gemini-2.5-flash"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["OAUTH_CLIENT_ID"] = "test-client-id"
os.environ["OAUTH_CLIENT_SECRET"] = "test-client-secret"
os.environ["OAUTH_REDIRECT_URI"] = "http://localhost:8080/auth/callback"
os.environ["OAUTH_DOMAIN_RESTRICTION"] = "false"
os.environ["OAUTH_ALLOWED_DOMAINS"] = "case.edu"

from app.main import app
from app.dependencies import get_firestore, get_current_user
from app.services.firestore_service import FirestoreService
from app.models.user import User
from app.models.conversation import Conversation, ConversationStatus
from app.models.feedback import Feedback, FeedbackVersion
from app.models.survey import Survey, HelpfulnessRating, LikelihoodRating


# ===== Mock Firestore Service =====

class MockFirestoreService:
    """
    Mock Firestore service for testing without real database connection.
    Stores data in memory dictionaries.
    """

    def __init__(self):
        self.users = {}
        self.conversations = {}
        self.feedback = {}
        self.surveys = {}
        self._counter = 0

    def _generate_id(self):
        self._counter += 1
        return f"test_id_{self._counter}"

    # User operations
    async def get_user_by_email(self, email: str):
        for user in self.users.values():
            if user.email == email:
                return user
        return None

    async def create_user(self, user_data):
        user_id = self._generate_id()
        user = User(
            user_id=user_id,
            email=user_data.email,
            name=user_data.name,
            domain=user_data.domain,
            picture_url=user_data.picture_url,
            created_at=datetime.utcnow(),
            last_login=datetime.utcnow(),
        )
        self.users[user_id] = user
        return user

    async def update_user_last_login(self, user_id: str):
        if user_id in self.users:
            self.users[user_id].last_login = datetime.utcnow()

    async def get_or_create_user(self, user_data):
        existing = await self.get_user_by_email(user_data.email)
        if existing:
            await self.update_user_last_login(existing.user_id)
            return existing
        return await self.create_user(user_data)

    # Conversation operations
    async def create_conversation(self, user_id: str, student_name: str, model: str):
        conv_id = self._generate_id()
        conversation = Conversation(
            conversation_id=conv_id,
            user_id=user_id,
            student_name=student_name,
            status=ConversationStatus.ACTIVE,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata={
                "model": model,
                "total_turns": 0,
                "project_id": "test-project",
                "environment": "test",
            },
            messages=[],
        )
        self.conversations[conv_id] = conversation
        return conversation

    async def get_conversation(self, conversation_id: str):
        return self.conversations.get(conversation_id)

    async def update_conversation_messages(self, conversation_id: str, messages: list, total_turns: int):
        if conversation_id in self.conversations:
            self.conversations[conversation_id].messages = messages
            self.conversations[conversation_id].metadata["total_turns"] = total_turns
            self.conversations[conversation_id].updated_at = datetime.utcnow()

    async def update_conversation_status(self, conversation_id: str, status):
        if conversation_id in self.conversations:
            self.conversations[conversation_id].status = status
            self.conversations[conversation_id].updated_at = datetime.utcnow()

    async def list_conversations(self, user_id: str, status=None, limit=20, offset=0):
        from app.models.conversation import ConversationSummary
        user_convs = [c for c in self.conversations.values() if c.user_id == user_id]
        if status:
            user_convs = [c for c in user_convs if c.status == status]
        user_convs.sort(key=lambda c: c.updated_at, reverse=True)
        paginated = user_convs[offset:offset + limit]

        summaries = []
        for conv in paginated:
            last_msg = conv.messages[-1]["content"] if conv.messages else ""
            has_feedback = conv.conversation_id in self.feedback
            summaries.append(ConversationSummary(
                conversation_id=conv.conversation_id,
                student_name=conv.student_name,
                status=conv.status,
                total_turns=conv.metadata["total_turns"],
                last_message_preview=last_msg[:100] if last_msg else None,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                has_feedback=has_feedback,
                feedback_preview=None,
            ))
        return summaries

    async def search_conversations(self, user_id: str, query: str, status=None, limit=20, offset=0):
        from app.models.conversation import ConversationSummary
        user_convs = [c for c in self.conversations.values() if c.user_id == user_id]
        query_lower = query.lower()
        user_convs = [c for c in user_convs if query_lower in c.student_name.lower()]
        if status:
            user_convs = [c for c in user_convs if c.status == status]
        user_convs.sort(key=lambda c: c.updated_at, reverse=True)
        paginated = user_convs[offset:offset + limit]

        summaries = []
        for conv in paginated:
            last_msg = conv.messages[-1]["content"] if conv.messages else ""
            has_feedback = conv.conversation_id in self.feedback
            summaries.append(ConversationSummary(
                conversation_id=conv.conversation_id,
                student_name=conv.student_name,
                status=conv.status,
                total_turns=conv.metadata["total_turns"],
                last_message_preview=last_msg[:100] if last_msg else None,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                has_feedback=has_feedback,
                feedback_preview=None,
            ))
        return summaries

    # Feedback operations
    async def create_feedback(self, conversation_id: str, user_id: str, student_name: str, initial_content: str):
        feedback_id = self._generate_id()
        initial_version = FeedbackVersion(
            version=1,
            timestamp=datetime.utcnow(),
            type="initial",
            content=initial_content,
            request=None,
        )
        feedback = Feedback(
            feedback_id=feedback_id,
            conversation_id=conversation_id,
            user_id=user_id,
            student_name=student_name,
            generated_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            versions=[initial_version],
            current_version=1,
        )
        self.feedback[conversation_id] = feedback

        # Update conversation
        if conversation_id in self.conversations:
            self.conversations[conversation_id].has_feedback = True

        return feedback

    async def add_feedback_refinement(self, feedback_id: str, refinement_content: str, refinement_request: str):
        for conv_id, fb in self.feedback.items():
            if fb.feedback_id == feedback_id:
                new_version = len(fb.versions) + 1
                new_version_obj = FeedbackVersion(
                    version=new_version,
                    timestamp=datetime.utcnow(),
                    type="refinement",
                    content=refinement_content,
                    request=refinement_request,
                )
                fb.versions.append(new_version_obj)
                fb.current_version = new_version
                fb.updated_at = datetime.utcnow()
                return fb
        raise ValueError(f"Feedback {feedback_id} not found")

    async def get_feedback_by_conversation(self, conversation_id: str):
        return self.feedback.get(conversation_id)

    # Survey operations
    async def create_survey(self, conversation_id: str, user_id: str, student_name: str, survey_data, skipped: bool = False):
        survey_id = self._generate_id()
        survey = Survey(
            survey_id=survey_id,
            conversation_id=conversation_id,
            user_id=user_id,
            student_name=student_name,
            helpfulness_rating=survey_data.helpfulness_rating,
            likelihood_rating=survey_data.likelihood_rating,
            comments=survey_data.comments,
            contact_name=survey_data.contact_name,
            contact_email=survey_data.contact_email,
            submitted_at=datetime.utcnow(),
            skipped=skipped,
        )
        self.surveys[conversation_id] = survey
        return survey

    async def get_survey_by_conversation(self, conversation_id: str):
        return self.surveys.get(conversation_id)

    async def get_surveys_by_user(self, user_id: str, limit: int = 50):
        user_surveys = [s for s in self.surveys.values() if s.user_id == user_id]
        user_surveys.sort(key=lambda s: s.submitted_at, reverse=True)
        return user_surveys[:limit]


# ===== Fixtures =====

@pytest.fixture
def mock_firestore():
    """Provides a mock Firestore service for testing."""
    return MockFirestoreService()


@pytest.fixture
def override_firestore(mock_firestore):
    """Override the Firestore dependency with mock."""
    def _get_mock_firestore():
        return mock_firestore
    return _get_mock_firestore


@pytest.fixture
def test_user():
    """Provides a test user."""
    return User(
        user_id="test_user_123",
        email="test@case.edu",
        name="Test User",
        domain="case.edu",
        picture_url="https://example.com/picture.jpg",
        created_at=datetime.utcnow(),
        last_login=datetime.utcnow(),
    )


@pytest.fixture
def test_user_2():
    """Provides a second test user for access control tests."""
    return User(
        user_id="test_user_456",
        email="test2@case.edu",
        name="Test User 2",
        domain="case.edu",
        picture_url="https://example.com/picture2.jpg",
        created_at=datetime.utcnow(),
        last_login=datetime.utcnow(),
    )


@pytest.fixture
def override_current_user(test_user):
    """Override current user dependency."""
    def _get_current_user():
        return {
            "user_id": test_user.user_id,
            "email": test_user.email,
            "name": test_user.name,
        }
    return _get_current_user


@pytest.fixture
async def client(override_firestore, override_current_user, mock_vertex_client):
    """
    Provides an async HTTP client for testing the FastAPI app.
    Overrides dependencies with test mocks.
    """
    app.dependency_overrides[get_firestore] = override_firestore
    app.dependency_overrides[get_current_user] = override_current_user

    # Mock VertexAIClient globally
    with patch("app.services.conversation_service.VertexAIClient", return_value=mock_vertex_client):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    # Cleanup
    app.dependency_overrides.clear()


@pytest.fixture
async def unauthenticated_client():
    """
    Provides an async HTTP client without authentication.
    Used for testing auth flows and protected routes.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_vertex_client():
    """Mock VertexAIClient for testing AI interactions."""
    mock = Mock()

    # Mock attributes
    mock.conversation_history = [
        {
            "timestamp": datetime.utcnow().isoformat(),
            "turn": "greeting",
            "role": "assistant",
            "content": "Thank you for sharing information about this student. What would you like to discuss?",
        }
    ]
    mock.turn_count = 0

    # Mock methods
    def mock_start_conversation():
        return "Thank you for sharing information about this student. What would you like to discuss?"

    def mock_set_student_name(name):
        pass

    mock.set_student_name = Mock(side_effect=mock_set_student_name)
    mock.start_conversation = Mock(side_effect=mock_start_conversation)
    mock.send_message = AsyncMock(return_value={
        "content": "Thank you for sharing that. Tell me more about the student's performance.",
        "contains_feedback": False,
    })
    mock.generate_feedback = AsyncMock(return_value="**Clerkship Director Summary**\n\nStrengths:\n- Good clinical reasoning\n\nAreas for Improvement:\n- Communication skills\n\n**Student-Facing Narrative**\n\nYou demonstrated strong clinical reasoning...")
    mock.refine_feedback = AsyncMock(return_value="**Clerkship Director Summary** (REFINED)\n\nStrengths:\n- Excellent clinical reasoning\n\nAreas for Improvement:\n- Communication skills\n\n**Student-Facing Narrative**\n\nYou demonstrated excellent clinical reasoning...")
    return mock


@pytest.fixture
def mock_jwt_token():
    """Generate a mock JWT token for testing."""
    from jose import jwt
    from app.config import settings

    payload = {
        "sub": "test@case.edu",
        "user_id": "test_user_123",
        "name": "Test User",
        "exp": datetime.utcnow() + timedelta(hours=24),
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token


@pytest.fixture
def auth_headers(mock_jwt_token):
    """Provides authenticated request headers with JWT cookie."""
    return {"Cookie": f"access_token={mock_jwt_token}"}


@pytest.fixture
def override_settings():
    """
    Context manager for temporarily overriding settings via environment variables.

    Usage in tests:
        def test_something(override_settings):
            with override_settings(OAUTH_DOMAIN_RESTRICTION="true", OAUTH_ALLOWED_DOMAINS="case.edu"):
                # Test code here
    """
    from contextlib import contextmanager

    @contextmanager
    def _override(**env_vars):
        # Store original values
        original_values = {}
        for key, value in env_vars.items():
            original_values[key] = os.environ.get(key)
            os.environ[key] = str(value)

        # Reload settings to pick up new env vars
        from importlib import reload
        from app import config
        reload(config)

        try:
            yield
        finally:
            # Restore original values
            for key, original_value in original_values.items():
                if original_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = original_value

            # Reload settings again to restore
            reload(config)

    return _override
