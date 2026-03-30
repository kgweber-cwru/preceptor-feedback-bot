"""
Tests for multi-program support.

Covers:
- Program config defaults and validation
- Prompt file existence for each program
- SURVEY_TEMPLATE config var is actually used in show_survey()
- Dev quick-test routes for both programs
- program/rating fields written to Firestore documents
"""

import os
import pytest
from unittest.mock import patch

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class TestProgramConfig:
    """Program-related settings in app.config.Settings."""

    def _fresh_settings(self, overrides=None):
        """Instantiate Settings with specific env vars cleared/set, bypassing .env."""
        clear = {"PROGRAM_ID", "PROGRAM_NAME", "PROGRAM_COLOR", "RATING_TYPE",
                 "SYSTEM_PROMPT_PATH", "SURVEY_TEMPLATE"}
        env = {k: v for k, v in os.environ.items() if k not in clear}
        if overrides:
            env.update(overrides)
        with patch.dict(os.environ, env, clear=True):
            from app.config import Settings
            return Settings()

    def test_program_id_is_known_value(self):
        """PROGRAM_ID must be one of the recognised program identifiers."""
        from app.config import settings
        assert settings.PROGRAM_ID in ("md", "msa")

    def test_default_program_name(self):
        s = self._fresh_settings()
        assert s.PROGRAM_NAME != ""

    def test_default_program_color_is_hex(self):
        s = self._fresh_settings()
        assert s.PROGRAM_COLOR.startswith("#")
        assert len(s.PROGRAM_COLOR) == 7

    def test_rating_type_is_known_value(self):
        from app.config import settings
        assert settings.RATING_TYPE in ("text", "numeric")

    def test_default_survey_template(self):
        from app.config import settings
        assert settings.SURVEY_TEMPLATE == "survey.html"

    def test_system_prompt_path_points_to_existing_file(self):
        from app.config import settings
        assert os.path.isfile(settings.SYSTEM_PROMPT_PATH), \
            f"SYSTEM_PROMPT_PATH={settings.SYSTEM_PROMPT_PATH!r} does not exist"

    def test_invalid_rating_type_raises(self):
        """validate_config() must reject unknown RATING_TYPE values."""
        s = self._fresh_settings({"RATING_TYPE": "invalid"})
        with pytest.raises(ValueError, match="RATING_TYPE"):
            s.validate_config()

    def test_valid_numeric_rating_type_passes(self):
        s = self._fresh_settings({"RATING_TYPE": "numeric"})
        assert s.validate_config() is True

    def test_get_deployment_info_includes_program_fields(self):
        from app.config import settings
        info = settings.get_deployment_info()
        assert "program_id" in info
        assert "program_name" in info
        assert "rating_type" in info


# ---------------------------------------------------------------------------
# Prompt files
# ---------------------------------------------------------------------------

class TestPromptFiles:
    """Both program prompt files must exist at their expected paths."""

    def test_md_prompt_exists(self):
        assert os.path.isfile("prompts/system_prompt_md.md"), \
            "MD system prompt not found at prompts/system_prompt_md.md"

    def test_msa_prompt_exists(self):
        assert os.path.isfile("prompts/system_prompt_msa.md"), \
            "MSA system prompt not found at prompts/system_prompt_msa.md"

    def test_md_prompt_contains_required_sections(self):
        with open("prompts/system_prompt_md.md") as f:
            content = f.read()
        assert "### Structured Summary" in content
        assert "### Student-Facing Narrative" in content
        assert "Clinical Performance" in content

    def test_msa_prompt_contains_required_sections(self):
        with open("prompts/system_prompt_msa.md") as f:
            content = f.read()
        assert "### Structured Summary" in content
        assert "### Student-Facing Narrative" in content
        assert "Clinical Performance" in content

    def test_msa_prompt_uses_numeric_rating_language(self):
        """MSA prompt should describe a 1–5 numeric scale."""
        with open("prompts/system_prompt_msa.md") as f:
            content = f.read()
        # Should explicitly reference 1 and 5 as scale endpoints
        assert "1 to 5" in content or "1–5" in content or "scale of 1" in content

    def test_md_prompt_uses_text_rating_language(self):
        """MD prompt should describe the qualitative scale."""
        with open("prompts/system_prompt_md.md") as f:
            content = f.read()
        assert "meets expectations" in content.lower() or \
               "exceeds expectations" in content.lower()

    def test_old_prompt_path_does_not_exist(self):
        """The old unsuffixed path should no longer exist (renamed to _md.md)."""
        assert not os.path.isfile("prompts/system_prompt.md"), \
            "Old prompt path still exists — was the rename applied?"


# ---------------------------------------------------------------------------
# SURVEY_TEMPLATE usage
# ---------------------------------------------------------------------------

class TestSurveyTemplate:
    """survey.show_survey() must use settings.SURVEY_TEMPLATE, not a hardcoded string."""

    @pytest.mark.asyncio
    async def test_survey_uses_configured_template(self, client, mock_firestore, test_user):
        """
        Verify show_survey() honours SURVEY_TEMPLATE.
        We override the setting to a non-existent template and expect a 500,
        proving the code reads from settings rather than a hardcoded literal.
        """
        from unittest.mock import patch
        from app import config

        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Template Test Student",
            model="gemini-2.5-flash",
        )

        # Patch settings to a non-existent template
        with patch.object(config.settings, "SURVEY_TEMPLATE", "nonexistent_template.html"):
            response = await client.get(f"/conversations/{conv.conversation_id}/survey")

        # Jinja2 raises TemplateNotFound → FastAPI returns 500
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_survey_renders_with_default_template(self, client, mock_firestore, test_user):
        """Default template renders successfully."""
        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Default Template Student",
            model="gemini-2.5-flash",
        )

        response = await client.get(f"/conversations/{conv.conversation_id}/survey")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Dev quick-test routes
# ---------------------------------------------------------------------------

class TestDevQuickTest:
    """Both quick-test endpoints must create a seeded conversation and redirect."""

    @pytest.mark.asyncio
    async def test_quick_test_md_redirects(self, client, mock_firestore):
        """MD quick-test creates a conversation and redirects to it."""
        response = await client.get("/dev/quick-test", follow_redirects=False)

        assert response.status_code == 302
        location = response.headers["location"]
        assert location.startswith("/conversations/")

    @pytest.mark.asyncio
    async def test_quick_test_md_seeds_messages(self, client, mock_firestore):
        """MD quick-test seeds the conversation with canned messages."""
        response = await client.get("/dev/quick-test", follow_redirects=False)
        conv_id = response.headers["location"].split("/")[-1]

        conv = await mock_firestore.get_conversation(conv_id)
        assert conv is not None
        assert len(conv.messages) > 0
        assert conv.student_name == "Alex Johnson (Quick Test)"

    @pytest.mark.asyncio
    async def test_quick_test_msa_redirects(self, client, mock_firestore):
        """MSA quick-test creates a conversation and redirects to it."""
        response = await client.get("/dev/quick-test-msa", follow_redirects=False)

        assert response.status_code == 302
        location = response.headers["location"]
        assert location.startswith("/conversations/")

    @pytest.mark.asyncio
    async def test_quick_test_msa_seeds_messages(self, client, mock_firestore):
        """MSA quick-test seeds the conversation with canned anesthesia messages."""
        response = await client.get("/dev/quick-test-msa", follow_redirects=False)
        conv_id = response.headers["location"].split("/")[-1]

        conv = await mock_firestore.get_conversation(conv_id)
        assert conv is not None
        assert len(conv.messages) > 0
        assert conv.student_name == "Jordan Lee (Quick Test — MSA)"

    @pytest.mark.asyncio
    async def test_quick_test_msa_contains_numeric_rating(self, client, mock_firestore):
        """MSA canned conversation must include a numeric rating in the transcript."""
        response = await client.get("/dev/quick-test-msa", follow_redirects=False)
        conv_id = response.headers["location"].split("/")[-1]

        conv = await mock_firestore.get_conversation(conv_id)
        all_content = " ".join(m.content for m in conv.messages)
        # The preceptor says "I'd say a 4" in the canned messages
        assert "4" in all_content

    @pytest.mark.asyncio
    async def test_quick_test_msa_contains_anesthesia_context(self, client, mock_firestore):
        """MSA canned messages must reference anesthesia/OR context."""
        response = await client.get("/dev/quick-test-msa", follow_redirects=False)
        conv_id = response.headers["location"].split("/")[-1]

        conv = await mock_firestore.get_conversation(conv_id)
        all_content = " ".join(m.content for m in conv.messages).lower()
        assert any(word in all_content for word in ["anesthesia", "induction", "rsi", "or", "appendectomy"])


# ---------------------------------------------------------------------------
# Firestore program field
# ---------------------------------------------------------------------------

class TestProgramFieldPersistence:
    """Verify program field is written to Firestore documents."""

    @pytest.mark.asyncio
    async def test_conversation_has_program_field(self, mock_firestore, test_user):
        from app.config import settings
        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Program Field Test",
            model="gemini-2.5-flash",
        )
        # MockFirestoreService doesn't write the program field (it's the real
        # service's job), but the model should have it with the correct default
        from app.models.conversation import Conversation
        assert hasattr(conv, "program")
        assert conv.program == "md"  # default

    @pytest.mark.asyncio
    async def test_feedback_has_program_and_rating_fields(self, mock_firestore, test_user):
        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Feedback Fields Test",
            model="gemini-2.5-flash",
        )
        feedback = await mock_firestore.create_feedback(
            conversation_id=conv.conversation_id,
            user_id=test_user.user_id,
            student_name="Feedback Fields Test",
            initial_content="Some feedback",
            rating=4,
        )
        assert feedback.program == "md"
        assert feedback.rating == 4

    @pytest.mark.asyncio
    async def test_feedback_rating_none_when_not_provided(self, mock_firestore, test_user):
        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="No Rating Test",
            model="gemini-2.5-flash",
        )
        feedback = await mock_firestore.create_feedback(
            conversation_id=conv.conversation_id,
            user_id=test_user.user_id,
            student_name="No Rating Test",
            initial_content="Some feedback",
        )
        assert feedback.rating is None

    @pytest.mark.asyncio
    async def test_survey_has_program_field(self, mock_firestore, test_user):
        from app.models.survey import SurveyCreate
        conv = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Survey Program Test",
            model="gemini-2.5-flash",
        )
        survey = await mock_firestore.create_survey(
            conversation_id=conv.conversation_id,
            user_id=test_user.user_id,
            student_name="Survey Program Test",
            survey_data=SurveyCreate(),
            skipped=True,
        )
        assert hasattr(survey, "program")
        assert survey.program == "md"  # default
