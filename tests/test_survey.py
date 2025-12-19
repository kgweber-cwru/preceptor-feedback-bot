"""
Integration tests for survey feature.
Tests survey display, submission, skip functionality, and data storage.
"""

import pytest
from app.models.survey import ToolRating

pytestmark = [pytest.mark.integration, pytest.mark.survey]


class TestSurveyAccess:
    """Tests for accessing survey page."""

    @pytest.mark.asyncio
    async def test_survey_page_shows_after_feedback(
        self, client, mock_firestore, test_user
    ):
        """Test that survey page is accessible after completing feedback."""
        # Create conversation and feedback
        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Survey Test Student",
            model="gemini-2.5-flash",
        )
        await mock_firestore.create_feedback(
            conversation_id=conv.conversation_id,
            user_id=test_user.user_id,
            student_name="Survey Test Student",
            initial_content="Feedback content",
        )

        response = await client.get(f"/conversations/{conv.conversation_id}/survey")

        assert response.status_code == 200
        assert "Survey Test Student" in response.text
        assert "How helpful was the tool?" in response.text or "tool" in response.text.lower()

    @pytest.mark.asyncio
    async def test_survey_shows_success_banner(
        self, client, mock_firestore, test_user
    ):
        """Test that survey page shows success banner for completed session."""
        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Success Banner Test",
            model="gemini-2.5-flash",
        )

        response = await client.get(f"/conversations/{conv.conversation_id}/survey")

        assert response.status_code == 200
        assert "Completed" in response.text or "saved" in response.text.lower()

    @pytest.mark.asyncio
    async def test_survey_for_nonexistent_conversation(self, client):
        """Test accessing survey for non-existent conversation fails."""
        response = await client.get("/conversations/nonexistent_id/survey")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_survey_redirects_if_already_submitted(
        self, client, mock_firestore, test_user
    ):
        """Test that accessing survey redirects if already submitted."""
        from app.models.survey import SurveyCreate

        # Create conversation
        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Already Submitted Test",
            model="gemini-2.5-flash",
        )

        # Create survey
        survey_data = SurveyCreate(
            preceptor_name="Dr. Test",
            tool_rating=ToolRating.GREAT_FIRST_TRY,
            comments="Test comment",
        )
        await mock_firestore.create_survey(
            conversation_id=conv.conversation_id,
            user_id=test_user.user_id,
            student_name="Already Submitted Test",
            survey_data=survey_data,
        )

        # Try to access survey again
        response = await client.get(
            f"/conversations/{conv.conversation_id}/survey",
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "/dashboard" in response.headers["location"]


class TestSurveySubmission:
    """Tests for submitting survey responses."""

    @pytest.mark.asyncio
    async def test_submit_complete_survey(self, client, mock_firestore, test_user):
        """Test submitting survey with all fields filled."""
        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Complete Survey Test",
            model="gemini-2.5-flash",
        )

        response = await client.post(
            f"/conversations/{conv.conversation_id}/survey",
            data={
                "preceptor_name": "Dr. John Smith",
                "tool_rating": "Was great on the first try",
                "comments": "Very helpful tool, saved me time!",
            },
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "/dashboard" in response.headers["location"]

        # Verify survey stored
        survey = await mock_firestore.get_survey_by_conversation(conv.conversation_id)
        assert survey is not None
        assert survey.preceptor_name == "Dr. John Smith"
        assert survey.tool_rating == ToolRating.GREAT_FIRST_TRY
        assert survey.comments == "Very helpful tool, saved me time!"
        assert survey.skipped is False

    @pytest.mark.asyncio
    async def test_submit_survey_with_required_only(
        self, client, mock_firestore, test_user
    ):
        """Test submitting survey with only required field (tool rating)."""
        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Minimal Survey Test",
            model="gemini-2.5-flash",
        )

        response = await client.post(
            f"/conversations/{conv.conversation_id}/survey",
            data={
                "tool_rating": "Gave me something helpful I can edit",
            },
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "/dashboard" in response.headers["location"]

        # Verify survey stored
        survey = await mock_firestore.get_survey_by_conversation(conv.conversation_id)
        assert survey is not None
        assert survey.preceptor_name is None
        assert survey.tool_rating == ToolRating.HELPFUL_WITH_EDITS
        assert survey.comments is None
        assert survey.skipped is False

    @pytest.mark.asyncio
    async def test_submit_survey_missing_required_field(
        self, client, mock_firestore, test_user
    ):
        """Test submitting survey without required tool_rating fails."""
        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Missing Rating Test",
            model="gemini-2.5-flash",
        )

        response = await client.post(
            f"/conversations/{conv.conversation_id}/survey",
            data={
                "preceptor_name": "Dr. Smith",
                "comments": "Good tool",
            },
        )

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_submit_survey_with_all_rating_options(
        self, client, mock_firestore, test_user
    ):
        """Test submitting survey with each rating option."""
        ratings = [
            "Was great on the first try",
            "Gave me something helpful I can edit",
            "Not especially helpful",
        ]

        for rating in ratings:
            conv = await mock_firestore.create_conversation(
                user_id=test_user.user_id,
                student_name=f"Rating Test - {rating}",
                model="gemini-2.5-flash",
            )

            response = await client.post(
                f"/conversations/{conv.conversation_id}/survey",
                data={"tool_rating": rating},
                follow_redirects=False,
            )

            assert response.status_code == 302

            # Verify survey stored
            survey = await mock_firestore.get_survey_by_conversation(conv.conversation_id)
            assert survey is not None
            assert survey.tool_rating.value == rating

    @pytest.mark.asyncio
    async def test_duplicate_survey_submission_redirects(
        self, client, mock_firestore, test_user
    ):
        """Test that submitting survey twice redirects without error."""
        from app.models.survey import SurveyCreate

        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Duplicate Submission Test",
            model="gemini-2.5-flash",
        )

        # Submit first survey
        survey_data = SurveyCreate(
            preceptor_name="Dr. First",
            tool_rating=ToolRating.GREAT_FIRST_TRY,
            comments="First submission",
        )
        await mock_firestore.create_survey(
            conversation_id=conv.conversation_id,
            user_id=test_user.user_id,
            student_name="Duplicate Submission Test",
            survey_data=survey_data,
        )

        # Try to submit again
        response = await client.post(
            f"/conversations/{conv.conversation_id}/survey",
            data={
                "preceptor_name": "Dr. Second",
                "tool_rating": "Not especially helpful",
                "comments": "Second submission",
            },
            follow_redirects=False,
        )

        # Should redirect without creating duplicate
        assert response.status_code == 302
        assert "/dashboard" in response.headers["location"]

        # Verify only one survey exists (the first one)
        survey = await mock_firestore.get_survey_by_conversation(conv.conversation_id)
        assert survey.preceptor_name == "Dr. First"
        assert survey.comments == "First submission"


class TestSurveySkip:
    """Tests for skipping survey."""

    @pytest.mark.asyncio
    async def test_skip_survey(self, client, mock_firestore, test_user):
        """Test skipping survey creates skipped record."""
        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Skip Test Student",
            model="gemini-2.5-flash",
        )

        response = await client.post(
            f"/conversations/{conv.conversation_id}/survey/skip",
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "/dashboard" in response.headers["location"]

        # Verify skip recorded
        survey = await mock_firestore.get_survey_by_conversation(conv.conversation_id)
        assert survey is not None
        assert survey.skipped is True
        assert survey.preceptor_name is None
        assert survey.comments is None

    @pytest.mark.asyncio
    async def test_skip_survey_redirects_to_dashboard(
        self, client, mock_firestore, test_user
    ):
        """Test that skipping survey redirects to dashboard."""
        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Skip Redirect Test",
            model="gemini-2.5-flash",
        )

        response = await client.post(
            f"/conversations/{conv.conversation_id}/survey/skip",
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert response.headers["location"] == "/dashboard"

    @pytest.mark.asyncio
    async def test_skip_already_skipped_survey(
        self, client, mock_firestore, test_user
    ):
        """Test skipping survey twice doesn't create duplicate."""
        from app.models.survey import SurveyCreate

        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Double Skip Test",
            model="gemini-2.5-flash",
        )

        # Skip first time
        survey_data = SurveyCreate(
            preceptor_name=None,
            tool_rating=ToolRating.GREAT_FIRST_TRY,
            comments=None,
        )
        await mock_firestore.create_survey(
            conversation_id=conv.conversation_id,
            user_id=test_user.user_id,
            student_name="Double Skip Test",
            survey_data=survey_data,
            skipped=True,
        )

        # Try to skip again
        response = await client.post(
            f"/conversations/{conv.conversation_id}/survey/skip",
            follow_redirects=False,
        )

        # Should redirect without error
        assert response.status_code == 302
        assert "/dashboard" in response.headers["location"]


class TestSurveyDataRetrieval:
    """Tests for retrieving survey data."""

    @pytest.mark.asyncio
    async def test_get_surveys_by_user(self, client, mock_firestore, test_user):
        """Test retrieving all surveys by user."""
        from app.models.survey import SurveyCreate

        # Create multiple conversations and surveys
        for i in range(3):
            conv = await mock_firestore.create_conversation(
                user_id=test_user.user_id,
                student_name=f"Student {i}",
                model="gemini-2.5-flash",
            )

            survey_data = SurveyCreate(
                preceptor_name=f"Dr. {i}",
                tool_rating=ToolRating.GREAT_FIRST_TRY,
                comments=f"Comment {i}",
            )
            await mock_firestore.create_survey(
                conversation_id=conv.conversation_id,
                user_id=test_user.user_id,
                student_name=f"Student {i}",
                survey_data=survey_data,
            )

        # Retrieve surveys
        surveys = await mock_firestore.get_surveys_by_user(test_user.user_id)

        assert len(surveys) == 3
        assert all(s.user_id == test_user.user_id for s in surveys)

    @pytest.mark.asyncio
    async def test_survey_timestamps_recorded(self, client, mock_firestore, test_user):
        """Test that survey submission timestamp is recorded."""
        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Timestamp Test",
            model="gemini-2.5-flash",
        )

        response = await client.post(
            f"/conversations/{conv.conversation_id}/survey",
            data={"tool_rating": "Was great on the first try"},
            follow_redirects=False,
        )

        assert response.status_code == 302

        survey = await mock_firestore.get_survey_by_conversation(conv.conversation_id)
        assert survey.submitted_at is not None
        assert survey.student_name == "Timestamp Test"
        assert survey.user_id == test_user.user_id
