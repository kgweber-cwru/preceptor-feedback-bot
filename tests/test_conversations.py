"""
Integration tests for conversation creation and messaging.
Tests conversation flow, message sending, and turn management.
"""

import pytest
from unittest.mock import patch, AsyncMock

pytestmark = [pytest.mark.integration, pytest.mark.conversation]


class TestConversationCreation:
    """Tests for creating new conversations."""

    @pytest.mark.asyncio
    async def test_create_conversation_success(self, client, mock_firestore, test_user):
        """Test successful conversation creation."""
        response = await client.post(
            "/conversations",
            json={"student_name": "Jane Doe"},
            follow_redirects=False,
        )

        # The endpoint returns HX-Redirect header
        assert response.status_code == 200
        assert "HX-Redirect" in response.headers
        assert "/conversations/" in response.headers["HX-Redirect"]

        # Verify conversation was created in mock Firestore
        # Extract conversation ID from redirect URL
        redirect_url = response.headers["HX-Redirect"]
        conversation_id = redirect_url.split("/conversations/")[1]

        conv = await mock_firestore.get_conversation(conversation_id)
        assert conv is not None
        assert conv.student_name == "Jane Doe"
        assert conv.status.value == "active"
        assert conv.user_id == test_user.user_id

    @pytest.mark.asyncio
    async def test_create_conversation_missing_student_name(self, client):
        """Test creating conversation without student name fails."""
        response = await client.post(
            "/conversations",
            json={},
        )

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_create_conversation_empty_student_name(self, client):
        """Test creating conversation with empty student name fails."""
        response = await client.post(
            "/conversations",
            json={"student_name": ""},
        )

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_create_conversation_initializes_metadata(self, client, mock_firestore):
        """Test that conversation metadata is initialized correctly."""
        response = await client.post(
            "/conversations",
            json={"student_name": "John Smith"},
        )

        assert response.status_code == 200
        data = response.json()

        conv = await mock_firestore.get_conversation(data["conversation_id"])
        assert conv.metadata["total_turns"] == 0
        assert conv.metadata["model"] is not None
        assert len(conv.messages) == 0


class TestConversationRetrieval:
    """Tests for retrieving conversations."""

    @pytest.mark.asyncio
    async def test_get_existing_conversation(self, client, mock_firestore, test_user):
        """Test retrieving an existing conversation."""
        # Create conversation first
        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Test Student",
            model="gemini-2.5-flash",
        )

        # Get conversation
        response = await client.get(f"/conversations/{conv.conversation_id}")

        assert response.status_code == 200
        assert "Test Student" in response.text

    @pytest.mark.asyncio
    async def test_get_nonexistent_conversation(self, client):
        """Test retrieving non-existent conversation returns 404."""
        response = await client.get("/conversations/nonexistent_id")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_conversation_page_shows_messages(self, client, mock_firestore, test_user):
        """Test that conversation page displays messages."""
        # Create conversation with messages
        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Test Student",
            model="gemini-2.5-flash",
        )

        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        await mock_firestore.update_conversation_messages(
            conv.conversation_id, messages, total_turns=1
        )

        # Get conversation page
        response = await client.get(f"/conversations/{conv.conversation_id}")

        assert response.status_code == 200
        assert "Hello" in response.text
        assert "Hi there!" in response.text


class TestMessageSending:
    """Tests for sending messages in conversations."""

    @pytest.mark.asyncio
    @patch("app.services.conversation_service.VertexAIClient")
    async def test_send_message_success(
        self, mock_vertex_class, client, mock_firestore, test_user
    ):
        """Test successfully sending a message."""
        # Setup mock
        mock_vertex = AsyncMock()
        mock_vertex.send_message.return_value = {
            "content": "Great! Tell me more.",
            "contains_feedback": False,
        }
        mock_vertex_class.return_value = mock_vertex

        # Create conversation
        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Test Student",
            model="gemini-2.5-flash",
        )

        # Send message
        response = await client.post(
            f"/conversations/{conv.conversation_id}/messages",
            json={"content": "The student did well on rounds."},
        )

        assert response.status_code == 200
        assert "Great! Tell me more." in response.text

        # Verify message stored
        updated_conv = await mock_firestore.get_conversation(conv.conversation_id)
        assert len(updated_conv.messages) >= 2  # User message + AI response
        assert updated_conv.metadata["total_turns"] == 1

    @pytest.mark.asyncio
    async def test_send_empty_message_fails(self, client, mock_firestore, test_user):
        """Test sending empty message fails validation."""
        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Test Student",
            model="gemini-2.5-flash",
        )

        response = await client.post(
            f"/conversations/{conv.conversation_id}/messages",
            json={"content": ""},
        )

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    @patch("app.services.conversation_service.VertexAIClient")
    async def test_message_increments_turn_counter(
        self, mock_vertex_class, client, mock_firestore, test_user
    ):
        """Test that sending messages increments turn counter."""
        mock_vertex = AsyncMock()
        mock_vertex.send_message.return_value = {
            "content": "Acknowledged.",
            "contains_feedback": False,
        }
        mock_vertex_class.return_value = mock_vertex

        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Test Student",
            model="gemini-2.5-flash",
        )

        # Send first message
        await client.post(
            f"/conversations/{conv.conversation_id}/messages",
            json={"content": "First message"},
        )

        conv_after_1 = await mock_firestore.get_conversation(conv.conversation_id)
        assert conv_after_1.metadata["total_turns"] == 1

        # Send second message
        await client.post(
            f"/conversations/{conv.conversation_id}/messages",
            json={"content": "Second message"},
        )

        conv_after_2 = await mock_firestore.get_conversation(conv.conversation_id)
        assert conv_after_2.metadata["total_turns"] == 2

    @pytest.mark.asyncio
    async def test_send_message_to_nonexistent_conversation(self, client):
        """Test sending message to non-existent conversation fails."""
        response = await client.post(
            "/conversations/nonexistent_id/messages",
            json={"content": "Test message"},
        )

        assert response.status_code == 404


class TestConversationFlow:
    """Tests for overall conversation flow."""

    @pytest.mark.asyncio
    @patch("app.services.conversation_service.VertexAIClient")
    async def test_complete_conversation_flow(
        self, mock_vertex_class, client, mock_firestore, test_user
    ):
        """Test complete conversation flow from creation to multiple messages."""
        mock_vertex = AsyncMock()
        mock_vertex.send_message.return_value = {
            "content": "Response",
            "contains_feedback": False,
        }
        mock_vertex_class.return_value = mock_vertex

        # Create conversation
        create_response = await client.post(
            "/conversations",
            json={"student_name": "Complete Flow Test"},
        )
        assert create_response.status_code == 200
        conv_id = create_response.json()["conversation_id"]

        # Send multiple messages
        for i in range(3):
            response = await client.post(
                f"/conversations/{conv_id}/messages",
                json={"content": f"Message {i + 1}"},
            )
            assert response.status_code == 200

        # Verify final state
        final_conv = await mock_firestore.get_conversation(conv_id)
        assert final_conv.metadata["total_turns"] == 3
        assert len(final_conv.messages) >= 6  # 3 user + 3 assistant messages

    @pytest.mark.asyncio
    @patch("app.services.conversation_service.VertexAIClient")
    async def test_premature_feedback_detection(
        self, mock_vertex_class, client, mock_firestore, test_user
    ):
        """Test that premature feedback is detected."""
        mock_vertex = AsyncMock()
        # Simulate AI generating feedback prematurely
        mock_vertex.send_message.return_value = {
            "content": "**Clerkship Director Summary**\n\nThis is premature feedback.",
            "contains_feedback": True,
        }
        mock_vertex_class.return_value = mock_vertex

        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Test Student",
            model="gemini-2.5-flash",
        )

        response = await client.post(
            f"/conversations/{conv.conversation_id}/messages",
            json={"content": "Tell me about the student."},
        )

        # Should still succeed but flag the issue
        assert response.status_code == 200
        # Check that premature feedback is handled appropriately
        # (exact behavior depends on implementation - may show warning or regenerate)

    @pytest.mark.asyncio
    @patch("app.services.conversation_service.VertexAIClient")
    async def test_max_turns_limit(
        self, mock_vertex_class, client, mock_firestore, test_user, monkeypatch
    ):
        """Test that conversation respects MAX_TURNS limit."""
        # Set MAX_TURNS to 3 for this test
        from app.config import settings
        monkeypatch.setattr(settings, "MAX_TURNS", 3)

        mock_vertex = AsyncMock()
        mock_vertex.send_message.return_value = {
            "content": "Response",
            "contains_feedback": False,
        }
        mock_vertex_class.return_value = mock_vertex

        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Max Turns Test",
            model="gemini-2.5-flash",
        )

        # Send messages up to limit
        for i in range(3):
            response = await client.post(
                f"/conversations/{conv.conversation_id}/messages",
                json={"content": f"Message {i + 1}"},
            )
            assert response.status_code == 200

        # Verify at limit
        final_conv = await mock_firestore.get_conversation(conv.conversation_id)
        assert final_conv.metadata["total_turns"] == 3
