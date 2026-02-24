"""
Integration tests for authorization and access control.
Tests that users can only access their own data and cannot access other users' data.
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.dependencies import get_firestore, get_current_user

pytestmark = [pytest.mark.integration, pytest.mark.auth]


class TestConversationAuthorization:
    """Tests for conversation access control."""

    @pytest.mark.asyncio
    async def test_user_cannot_access_other_users_conversation(
        self, mock_firestore, test_user, test_user_2
    ):
        """Test that user cannot access another user's conversation."""
        # Create conversation for user 1
        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="User 1's Student",
            model="gemini-2.5-flash",
        )

        # Try to access as user 2
        def get_user_2():
            return {
                "user_id": test_user_2.user_id,
                "email": test_user_2.email,
                "name": test_user_2.name,
            }

        def get_mock_firestore():
            return mock_firestore

        app.dependency_overrides[get_firestore] = get_mock_firestore
        app.dependency_overrides[get_current_user] = get_user_2

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/conversations/{conv.conversation_id}")

        app.dependency_overrides.clear()

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_user_can_access_own_conversation(
        self, client, mock_firestore, test_user
    ):
        """Test that user can access their own conversation."""
        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="User's Own Student",
            model="gemini-2.5-flash",
        )

        response = await client.get(f"/conversations/{conv.conversation_id}")

        assert response.status_code == 200
        assert "User's Own Student" in response.text

    @pytest.mark.asyncio
    async def test_user_cannot_send_message_to_other_users_conversation(
        self, mock_firestore, test_user, test_user_2
    ):
        """Test that user cannot send message to another user's conversation."""
        # Create conversation for user 1
        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="User 1's Student",
            model="gemini-2.5-flash",
        )

        # Try to send message as user 2
        def get_user_2():
            return {
                "user_id": test_user_2.user_id,
                "email": test_user_2.email,
                "name": test_user_2.name,
            }

        def get_mock_firestore():
            return mock_firestore

        app.dependency_overrides[get_firestore] = get_mock_firestore
        app.dependency_overrides[get_current_user] = get_user_2

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/conversations/{conv.conversation_id}/messages",
                json={"content": "Unauthorized message"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 403


class TestFeedbackAuthorization:
    """Tests for feedback access control."""

    @pytest.mark.asyncio
    async def test_user_cannot_access_other_users_feedback(
        self, mock_firestore, test_user, test_user_2
    ):
        """Test that user cannot access another user's feedback."""
        # Create conversation and feedback for user 1
        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="User 1's Student",
            model="gemini-2.5-flash",
        )
        await mock_firestore.create_feedback(
            conversation_id=conv.conversation_id,
            user_id=test_user.user_id,
            student_name="User 1's Student",
            initial_content="Feedback for user 1",
        )

        # Try to access as user 2
        def get_user_2():
            return {
                "user_id": test_user_2.user_id,
                "email": test_user_2.email,
                "name": test_user_2.name,
            }

        def get_mock_firestore():
            return mock_firestore

        app.dependency_overrides[get_firestore] = get_mock_firestore
        app.dependency_overrides[get_current_user] = get_user_2

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/conversations/{conv.conversation_id}/feedback")

        app.dependency_overrides.clear()

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_user_cannot_refine_other_users_feedback(
        self, mock_firestore, test_user, test_user_2
    ):
        """Test that user cannot refine another user's feedback."""
        # Create conversation and feedback for user 1
        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="User 1's Student",
            model="gemini-2.5-flash",
        )
        await mock_firestore.create_feedback(
            conversation_id=conv.conversation_id,
            user_id=test_user.user_id,
            student_name="User 1's Student",
            initial_content="Feedback for user 1",
        )

        # Try to refine as user 2
        def get_user_2():
            return {
                "user_id": test_user_2.user_id,
                "email": test_user_2.email,
                "name": test_user_2.name,
            }

        def get_mock_firestore():
            return mock_firestore

        app.dependency_overrides[get_firestore] = get_mock_firestore
        app.dependency_overrides[get_current_user] = get_user_2

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/conversations/{conv.conversation_id}/feedback/refine",
                json={"refinement_request": "Unauthorized refinement"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_user_cannot_download_other_users_feedback(
        self, mock_firestore, test_user, test_user_2
    ):
        """Test that user cannot download another user's feedback."""
        # Create conversation and feedback for user 1
        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="User 1's Student",
            model="gemini-2.5-flash",
        )
        await mock_firestore.create_feedback(
            conversation_id=conv.conversation_id,
            user_id=test_user.user_id,
            student_name="User 1's Student",
            initial_content="Feedback for user 1",
        )

        # Try to download as user 2
        def get_user_2():
            return {
                "user_id": test_user_2.user_id,
                "email": test_user_2.email,
                "name": test_user_2.name,
            }

        def get_mock_firestore():
            return mock_firestore

        app.dependency_overrides[get_firestore] = get_mock_firestore
        app.dependency_overrides[get_current_user] = get_user_2

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/conversations/{conv.conversation_id}/feedback/download"
            )

        app.dependency_overrides.clear()

        assert response.status_code == 403


class TestDashboardAuthorization:
    """Tests for dashboard and conversation list access control."""

    @pytest.mark.asyncio
    async def test_user_only_sees_own_conversations(
        self, mock_firestore, test_user, test_user_2
    ):
        """Test that user only sees their own conversations in list."""
        # Create conversations for user 1
        await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="User 1 Student A",
            model="gemini-2.5-flash",
        )
        await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="User 1 Student B",
            model="gemini-2.5-flash",
        )

        # Create conversation for user 2
        await mock_firestore.create_conversation(
            user_id=test_user_2.user_id,
            student_name="User 2 Student",
            model="gemini-2.5-flash",
        )

        # Get conversations as user 1
        def get_user_1():
            return {
                "user_id": test_user.user_id,
                "email": test_user.email,
                "name": test_user.name,
            }

        def get_mock_firestore():
            return mock_firestore

        app.dependency_overrides[get_firestore] = get_mock_firestore
        app.dependency_overrides[get_current_user] = get_user_1

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/conversations")

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert len(data["conversations"]) == 2

        student_names = [c["student_name"] for c in data["conversations"]]
        assert "User 1 Student A" in student_names
        assert "User 1 Student B" in student_names
        assert "User 2 Student" not in student_names

    @pytest.mark.asyncio
    async def test_search_only_searches_own_conversations(
        self, mock_firestore, test_user, test_user_2
    ):
        """Test that search only searches user's own conversations."""
        # Create conversations for user 1
        await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Alice Johnson",
            model="gemini-2.5-flash",
        )

        # Create conversation for user 2 with similar name
        await mock_firestore.create_conversation(
            user_id=test_user_2.user_id,
            student_name="Alice Smith",
            model="gemini-2.5-flash",
        )

        # Search as user 1 for "Alice"
        def get_user_1():
            return {
                "user_id": test_user.user_id,
                "email": test_user.email,
                "name": test_user.name,
            }

        def get_mock_firestore():
            return mock_firestore

        app.dependency_overrides[get_firestore] = get_mock_firestore
        app.dependency_overrides[get_current_user] = get_user_1

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/conversations?search=Alice")

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert len(data["conversations"]) == 1
        assert data["conversations"][0]["student_name"] == "Alice Johnson"


class TestSurveyAuthorization:
    """Tests for survey access control."""

    @pytest.mark.asyncio
    async def test_user_cannot_access_other_users_survey(
        self, mock_firestore, test_user, test_user_2
    ):
        """Test that user cannot access survey for another user's conversation."""
        # Create conversation for user 1
        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="User 1's Student",
            model="gemini-2.5-flash",
        )

        # Try to access survey as user 2
        def get_user_2():
            return {
                "user_id": test_user_2.user_id,
                "email": test_user_2.email,
                "name": test_user_2.name,
            }

        def get_mock_firestore():
            return mock_firestore

        app.dependency_overrides[get_firestore] = get_mock_firestore
        app.dependency_overrides[get_current_user] = get_user_2

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/conversations/{conv.conversation_id}/survey")

        app.dependency_overrides.clear()

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_user_cannot_submit_survey_for_other_users_conversation(
        self, mock_firestore, test_user, test_user_2
    ):
        """Test that user cannot submit survey for another user's conversation."""
        # Create conversation for user 1
        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="User 1's Student",
            model="gemini-2.5-flash",
        )

        # Try to submit survey as user 2
        def get_user_2():
            return {
                "user_id": test_user_2.user_id,
                "email": test_user_2.email,
                "name": test_user_2.name,
            }

        def get_mock_firestore():
            return mock_firestore

        app.dependency_overrides[get_firestore] = get_mock_firestore
        app.dependency_overrides[get_current_user] = get_user_2

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/conversations/{conv.conversation_id}/survey",
                data={
                    "helpfulness_rating": "Very helpful",
                    "likelihood_rating": "Likely",
                    "comments": "Unauthorized survey",
                },
            )

        app.dependency_overrides.clear()

        assert response.status_code == 403
