"""
Integration tests for feedback generation and refinement.
Tests feedback creation, versioning, refinement, and download.
"""

import pytest
from unittest.mock import patch, AsyncMock, Mock
import tempfile
import os

pytestmark = [pytest.mark.integration, pytest.mark.feedback]


class TestFeedbackGeneration:
    """Tests for generating feedback from conversations."""

    @pytest.mark.asyncio
    @patch("app.services.conversation_service.VertexAIClient")
    async def test_generate_feedback_success(
        self, mock_vertex_class, client, mock_firestore, test_user
    ):
        """Test successful feedback generation."""
        # Setup mock
        mock_vertex = AsyncMock()
        mock_vertex.generate_feedback.return_value = (
            "**Clerkship Director Summary**\n\nStrengths:\n- Good clinical reasoning\n\n"
            "**Student-Facing Narrative**\n\nYou demonstrated good clinical reasoning."
        )
        mock_vertex_class.return_value = mock_vertex

        # Create conversation with some messages
        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Test Student",
            model="gemini-2.5-flash",
        )
        messages = [
            {"role": "user", "content": "The student did well."},
            {"role": "assistant", "content": "Tell me more."},
        ]
        await mock_firestore.update_conversation_messages(
            conv.conversation_id, messages, total_turns=1
        )

        # Generate feedback
        response = await client.get(f"/conversations/{conv.conversation_id}/feedback")

        assert response.status_code == 200
        assert "Clerkship Director Summary" in response.text
        assert "Student-Facing Narrative" in response.text
        assert "Test Student" in response.text

        # Verify feedback stored in Firestore
        feedback = await mock_firestore.get_feedback_by_conversation(conv.conversation_id)
        assert feedback is not None
        assert feedback.student_name == "Test Student"
        assert feedback.current_version == 1
        assert len(feedback.versions) == 1

    @pytest.mark.asyncio
    async def test_generate_feedback_for_nonexistent_conversation(self, client):
        """Test generating feedback for non-existent conversation fails."""
        response = await client.get("/conversations/nonexistent_id/feedback")

        assert response.status_code == 404

    @pytest.mark.asyncio
    @patch("app.services.conversation_service.VertexAIClient")
    async def test_generate_feedback_shows_existing_feedback(
        self, mock_vertex_class, client, mock_firestore, test_user
    ):
        """Test that requesting feedback shows existing feedback if already generated."""
        mock_vertex = AsyncMock()
        mock_vertex_class.return_value = mock_vertex

        # Create conversation
        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Test Student",
            model="gemini-2.5-flash",
        )

        # Create feedback manually
        existing_feedback = await mock_firestore.create_feedback(
            conversation_id=conv.conversation_id,
            user_id=test_user.user_id,
            student_name="Test Student",
            initial_content="Existing feedback content",
        )

        # Request feedback page
        response = await client.get(f"/conversations/{conv.conversation_id}/feedback")

        assert response.status_code == 200
        assert "Existing feedback content" in response.text
        # Should not generate new feedback
        mock_vertex.generate_feedback.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.services.conversation_service.VertexAIClient")
    async def test_feedback_marks_conversation_as_having_feedback(
        self, mock_vertex_class, client, mock_firestore, test_user
    ):
        """Test that generating feedback marks conversation with has_feedback flag."""
        mock_vertex = AsyncMock()
        mock_vertex.generate_feedback.return_value = "Generated feedback"
        mock_vertex_class.return_value = mock_vertex

        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Test Student",
            model="gemini-2.5-flash",
        )

        # Initially should not have feedback
        assert not getattr(conv, "has_feedback", False)

        # Generate feedback
        await client.get(f"/conversations/{conv.conversation_id}/feedback")

        # Should now have feedback flag
        updated_conv = await mock_firestore.get_conversation(conv.conversation_id)
        assert getattr(updated_conv, "has_feedback", False) is True


class TestFeedbackRefinement:
    """Tests for refining existing feedback."""

    @pytest.mark.asyncio
    @patch("app.services.conversation_service.VertexAIClient")
    async def test_refine_feedback_success(
        self, mock_vertex_class, client, mock_firestore, test_user
    ):
        """Test successful feedback refinement."""
        mock_vertex = AsyncMock()
        mock_vertex.refine_feedback.return_value = "Refined feedback content with more detail"
        mock_vertex_class.return_value = mock_vertex

        # Create conversation and feedback
        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Test Student",
            model="gemini-2.5-flash",
        )
        feedback = await mock_firestore.create_feedback(
            conversation_id=conv.conversation_id,
            user_id=test_user.user_id,
            student_name="Test Student",
            initial_content="Original feedback",
        )

        # Refine feedback
        response = await client.post(
            f"/conversations/{conv.conversation_id}/feedback/refine",
            json={"refinement_request": "Add more detail about communication"},
        )

        assert response.status_code == 200
        assert "Refined feedback content" in response.text

        # Verify version incremented
        updated_feedback = await mock_firestore.get_feedback_by_conversation(conv.conversation_id)
        assert updated_feedback.current_version == 2
        assert len(updated_feedback.versions) == 2
        assert updated_feedback.versions[1].type == "refinement"
        assert updated_feedback.versions[1].request == "Add more detail about communication"

    @pytest.mark.asyncio
    async def test_refine_feedback_empty_request_fails(
        self, client, mock_firestore, test_user
    ):
        """Test refining feedback with empty request fails."""
        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Test Student",
            model="gemini-2.5-flash",
        )
        await mock_firestore.create_feedback(
            conversation_id=conv.conversation_id,
            user_id=test_user.user_id,
            student_name="Test Student",
            initial_content="Original feedback",
        )

        response = await client.post(
            f"/conversations/{conv.conversation_id}/feedback/refine",
            json={"refinement_request": ""},
        )

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    @patch("app.services.conversation_service.VertexAIClient")
    async def test_multiple_refinements(
        self, mock_vertex_class, client, mock_firestore, test_user
    ):
        """Test multiple feedback refinements create multiple versions."""
        mock_vertex = AsyncMock()
        mock_vertex.refine_feedback.side_effect = [
            "Refinement 1",
            "Refinement 2",
            "Refinement 3",
        ]
        mock_vertex_class.return_value = mock_vertex

        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Test Student",
            model="gemini-2.5-flash",
        )
        await mock_firestore.create_feedback(
            conversation_id=conv.conversation_id,
            user_id=test_user.user_id,
            student_name="Test Student",
            initial_content="Original",
        )

        # Perform three refinements
        for i in range(3):
            response = await client.post(
                f"/conversations/{conv.conversation_id}/feedback/refine",
                json={"refinement_request": f"Request {i + 1}"},
            )
            assert response.status_code == 200

        # Verify versions
        final_feedback = await mock_firestore.get_feedback_by_conversation(conv.conversation_id)
        assert final_feedback.current_version == 4  # 1 initial + 3 refinements
        assert len(final_feedback.versions) == 4


class TestFeedbackDownload:
    """Tests for downloading feedback as text file."""

    @pytest.mark.asyncio
    async def test_download_feedback_success(self, client, mock_firestore, test_user):
        """Test downloading feedback as text file."""
        # Create conversation and feedback
        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Download Test Student",
            model="gemini-2.5-flash",
        )
        await mock_firestore.create_feedback(
            conversation_id=conv.conversation_id,
            user_id=test_user.user_id,
            student_name="Download Test Student",
            initial_content="**Feedback Content**\n\nThis is the feedback to download.",
        )

        # Download feedback
        response = await client.get(
            f"/conversations/{conv.conversation_id}/feedback/download"
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/plain; charset=utf-8"
        assert "attachment" in response.headers.get("content-disposition", "")
        assert "Download_Test_Student" in response.headers.get("content-disposition", "")

        # Check content
        content = response.text
        assert "Download Test Student" in content
        assert "Feedback Content" in content

    @pytest.mark.asyncio
    async def test_download_nonexistent_feedback(self, client, mock_firestore, test_user):
        """Test downloading feedback for conversation without feedback fails."""
        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="No Feedback Student",
            model="gemini-2.5-flash",
        )

        response = await client.get(
            f"/conversations/{conv.conversation_id}/feedback/download"
        )

        assert response.status_code == 404


class TestFeedbackFinish:
    """Tests for finishing conversation after feedback."""

    @pytest.mark.asyncio
    async def test_finish_marks_conversation_completed(
        self, client, mock_firestore, test_user
    ):
        """Test that finishing conversation marks it as completed."""
        from app.models.conversation import ConversationStatus

        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Finish Test Student",
            model="gemini-2.5-flash",
        )
        await mock_firestore.create_feedback(
            conversation_id=conv.conversation_id,
            user_id=test_user.user_id,
            student_name="Finish Test Student",
            initial_content="Feedback",
        )

        # Finish conversation
        response = await client.post(
            f"/conversations/{conv.conversation_id}/finish",
            follow_redirects=False,
        )

        # Should redirect (either HTMX redirect header or standard redirect)
        assert response.status_code in [200, 302]

        # Verify status updated
        updated_conv = await mock_firestore.get_conversation(conv.conversation_id)
        assert updated_conv.status == ConversationStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_finish_redirects_to_survey(self, client, mock_firestore, test_user):
        """Test that finishing redirects to survey page."""
        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Survey Redirect Test",
            model="gemini-2.5-flash",
        )
        await mock_firestore.create_feedback(
            conversation_id=conv.conversation_id,
            user_id=test_user.user_id,
            student_name="Survey Redirect Test",
            initial_content="Feedback",
        )

        response = await client.post(
            f"/conversations/{conv.conversation_id}/finish",
            follow_redirects=False,
        )

        # Check for redirect to survey (either in header or HX-Redirect header)
        assert response.status_code in [200, 302]
        if response.status_code == 200:
            # HTMX redirect
            assert "HX-Redirect" in response.headers
            assert f"/conversations/{conv.conversation_id}/survey" in response.headers["HX-Redirect"]
        else:
            # Standard redirect
            assert f"/conversations/{conv.conversation_id}/survey" in response.headers["location"]
