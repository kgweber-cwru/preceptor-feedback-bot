"""
Integration tests for survey feature.
Tests survey display, submission, skip functionality, and data storage.
"""

import pytest
from app.models.survey import HelpfulnessRating, LikelihoodRating

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
            helpfulness_rating=HelpfulnessRating.VERY_HELPFUL,
            likelihood_rating=LikelihoodRating.LIKELY,
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
                "helpfulness_rating": "Very helpful",
                "likelihood_rating": "Likely",
                "comments": "Very helpful tool, saved me time!",
                "contact_name": "Dr. John Smith",
                "contact_email": "john.smith@example.com",
            },
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "/dashboard" in response.headers["location"]

        # Verify survey stored
        survey = await mock_firestore.get_survey_by_conversation(conv.conversation_id)
        assert survey is not None
        assert survey.helpfulness_rating == HelpfulnessRating.VERY_HELPFUL
        assert survey.likelihood_rating == LikelihoodRating.LIKELY
        assert survey.comments == "Very helpful tool, saved me time!"
        assert survey.contact_name == "Dr. John Smith"
        assert survey.contact_email == "john.smith@example.com"
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
                "helpfulness_rating": "Moderately helpful",
                "likelihood_rating": "Neutral",
            },
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "/dashboard" in response.headers["location"]

        # Verify survey stored
        survey = await mock_firestore.get_survey_by_conversation(conv.conversation_id)
        assert survey is not None
        assert survey.helpfulness_rating == HelpfulnessRating.MODERATELY_HELPFUL
        assert survey.likelihood_rating == LikelihoodRating.NEUTRAL
        assert survey.comments is None
        assert survey.contact_name is None
        assert survey.skipped is False

    @pytest.mark.asyncio
    async def test_submit_survey_missing_required_field(
        self, client, mock_firestore, test_user
    ):
        """Test submitting survey without required rating fields fails."""
        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Missing Rating Test",
            model="gemini-2.5-flash",
        )

        response = await client.post(
            f"/conversations/{conv.conversation_id}/survey",
            data={
                "comments": "Good tool",
            },
        )

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_submit_survey_with_all_rating_options(
        self, client, mock_firestore, test_user
    ):
        """Test submitting survey with each helpfulness and likelihood rating option."""
        helpfulness_ratings = [
            "Not at all helpful",
            "Slightly helpful",
            "Moderately helpful",
            "Very helpful",
            "Extremely helpful",
        ]
        likelihood_ratings = [
            "Very unlikely",
            "Unlikely",
            "Neutral",
            "Likely",
            "Very likely",
        ]

        for h_rating, l_rating in zip(helpfulness_ratings, likelihood_ratings):
            conv = await mock_firestore.create_conversation(
                user_id=test_user.user_id,
                student_name=f"Rating Test - {h_rating}",
                model="gemini-2.5-flash",
            )

            response = await client.post(
                f"/conversations/{conv.conversation_id}/survey",
                data={"helpfulness_rating": h_rating, "likelihood_rating": l_rating},
                follow_redirects=False,
            )

            assert response.status_code == 302

            # Verify survey stored
            survey = await mock_firestore.get_survey_by_conversation(conv.conversation_id)
            assert survey is not None
            assert survey.helpfulness_rating.value == h_rating
            assert survey.likelihood_rating.value == l_rating

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
            helpfulness_rating=HelpfulnessRating.VERY_HELPFUL,
            likelihood_rating=LikelihoodRating.LIKELY,
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
                "helpfulness_rating": "Not at all helpful",
                "likelihood_rating": "Very unlikely",
                "comments": "Second submission",
            },
            follow_redirects=False,
        )

        # Should redirect without creating duplicate
        assert response.status_code == 302
        assert "/dashboard" in response.headers["location"]

        # Verify only one survey exists (the first one)
        survey = await mock_firestore.get_survey_by_conversation(conv.conversation_id)
        assert survey.helpfulness_rating == HelpfulnessRating.VERY_HELPFUL
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
        assert survey.helpfulness_rating is None
        assert survey.likelihood_rating is None
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
        survey_data = SurveyCreate()
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
                helpfulness_rating=HelpfulnessRating.EXTREMELY_HELPFUL,
                likelihood_rating=LikelihoodRating.VERY_LIKELY,
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
            data={
                "helpfulness_rating": "Very helpful",
                "likelihood_rating": "Likely",
            },
            follow_redirects=False,
        )

        assert response.status_code == 302

        survey = await mock_firestore.get_survey_by_conversation(conv.conversation_id)
        assert survey.submitted_at is not None
        assert survey.student_name == "Timestamp Test"
        assert survey.user_id == test_user.user_id
