"""
Unit tests for VertexAIClient pure methods.

These tests exercise logic that does not require a live GCP connection.
The genai.Client is patched out so the constructor succeeds in CI/test environments.
"""

import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Fixture: a VertexAIClient instance with GCP stubbed out
# ---------------------------------------------------------------------------

@pytest.fixture
def ai_client():
    """VertexAIClient with GCP client mocked — real system prompt loaded from disk."""
    with patch("app.services.vertex_ai_client.genai.Client"):
        from app.services.vertex_ai_client import VertexAIClient
        return VertexAIClient()


# ---------------------------------------------------------------------------
# _extract_rating
# ---------------------------------------------------------------------------

class TestExtractRating:

    def test_text_type_returns_string(self, ai_client):
        text = "* **Clinical Performance**: Meets Expectations"
        with patch("app.services.vertex_ai_client.settings") as mock_settings:
            mock_settings.RATING_TYPE = "text"
            result = ai_client._extract_rating(text)
        assert result == "Meets Expectations"

    def test_text_type_exceeds(self, ai_client):
        text = "* **Clinical Performance**: Exceeds Expectations"
        with patch("app.services.vertex_ai_client.settings") as mock_settings:
            mock_settings.RATING_TYPE = "text"
            result = ai_client._extract_rating(text)
        assert result == "Exceeds Expectations"

    def test_text_type_does_not_meet(self, ai_client):
        text = "* **Clinical Performance**: Does Not Meet Expectations"
        with patch("app.services.vertex_ai_client.settings") as mock_settings:
            mock_settings.RATING_TYPE = "text"
            result = ai_client._extract_rating(text)
        assert result == "Does Not Meet Expectations"

    def test_numeric_fraction_format(self, ai_client):
        text = "* **Clinical Performance**: 4/5"
        with patch("app.services.vertex_ai_client.settings") as mock_settings:
            mock_settings.RATING_TYPE = "numeric"
            result = ai_client._extract_rating(text)
        assert result == 4

    def test_numeric_plain_integer(self, ai_client):
        text = "* **Clinical Performance**: 3"
        with patch("app.services.vertex_ai_client.settings") as mock_settings:
            mock_settings.RATING_TYPE = "numeric"
            result = ai_client._extract_rating(text)
        assert result == 3

    def test_numeric_prose_format(self, ai_client):
        text = "* **Clinical Performance**: 5 out of 5"
        with patch("app.services.vertex_ai_client.settings") as mock_settings:
            mock_settings.RATING_TYPE = "numeric"
            result = ai_client._extract_rating(text)
        assert result == 5

    def test_numeric_non_parseable_returns_none(self, ai_client):
        text = "* **Clinical Performance**: N/A"
        with patch("app.services.vertex_ai_client.settings") as mock_settings:
            mock_settings.RATING_TYPE = "numeric"
            result = ai_client._extract_rating(text)
        assert result is None

    def test_missing_marker_returns_none(self, ai_client):
        text = "* **Strengths**: Good clinical reasoning"
        with patch("app.services.vertex_ai_client.settings") as mock_settings:
            mock_settings.RATING_TYPE = "text"
            result = ai_client._extract_rating(text)
        assert result is None

    def test_empty_string_returns_none(self, ai_client):
        with patch("app.services.vertex_ai_client.settings") as mock_settings:
            mock_settings.RATING_TYPE = "text"
            result = ai_client._extract_rating("")
        assert result is None

    def test_marker_present_but_empty_value_returns_none(self, ai_client):
        text = "* **Clinical Performance**: "
        with patch("app.services.vertex_ai_client.settings") as mock_settings:
            mock_settings.RATING_TYPE = "text"
            result = ai_client._extract_rating(text)
        assert result is None

    def test_embedded_in_full_feedback_block(self, ai_client):
        text = (
            "### Structured Summary\n\n"
            "* **Context of evaluation**: Outpatient clinic\n"
            "* **Strengths**:\n"
            "  * **Patient Care**: Excellent history taking\n"
            "* **Areas for Improvement**: Oral presentations\n"
            "* **Clinical Performance**: Meets Expectations\n\n"
            "### Student-Facing Narrative\n\nYou did well."
        )
        with patch("app.services.vertex_ai_client.settings") as mock_settings:
            mock_settings.RATING_TYPE = "text"
            result = ai_client._extract_rating(text)
        assert result == "Meets Expectations"


# ---------------------------------------------------------------------------
# _contains_formal_feedback
# ---------------------------------------------------------------------------

class TestContainsFormalFeedback:

    def test_returns_true_with_many_markers(self, ai_client):
        text = (
            "**Structured Summary**\n"
            "**Student-Facing Narrative**\n"
            "**Strengths**\n"
            "**Areas for Improvement**\n"
        )
        assert ai_client._contains_formal_feedback(text) is True

    def test_returns_false_with_fewer_than_three_markers(self, ai_client):
        text = "**Strengths** **Areas for Improvement**"
        assert ai_client._contains_formal_feedback(text) is False

    def test_returns_false_for_normal_conversation(self, ai_client):
        text = "That's great! Can you tell me more about the student's clinical reasoning?"
        assert ai_client._contains_formal_feedback(text) is False

    def test_returns_true_at_exact_threshold(self, ai_client):
        # Exactly 3 markers — should trigger
        text = "**Structured Summary **Student-Facing Narrative **Strengths**"
        assert ai_client._contains_formal_feedback(text) is True

    def test_returns_false_with_two_markers(self, ai_client):
        text = "**Structured Summary\n**Student-Facing Narrative"
        assert ai_client._contains_formal_feedback(text) is False

    def test_empty_string(self, ai_client):
        assert ai_client._contains_formal_feedback("") is False


# ---------------------------------------------------------------------------
# _fix_markdown_formatting
# ---------------------------------------------------------------------------

class TestFixMarkdownFormatting:

    def test_definition_list_converted_to_bullet(self, ai_client):
        text = "Context of evaluation\n: Outpatient clinic, 30 minutes"
        result = ai_client._fix_markdown_formatting(text)
        assert "* **Context of evaluation**: Outpatient clinic, 30 minutes" in result

    def test_header_only_definition_list_creates_sub_bullets(self, ai_client):
        text = "Strengths\n:\nPatient Care\n: Excellent"
        result = ai_client._fix_markdown_formatting(text)
        assert "* **Strengths**:" in result
        assert "  * **Patient Care**: Excellent" in result

    def test_blank_line_inserted_after_heading(self, ai_client):
        text = "### Structured Summary\nFirst line after heading"
        result = ai_client._fix_markdown_formatting(text)
        assert "### Structured Summary\n\nFirst line" in result

    def test_already_formatted_bullet_passes_through(self, ai_client):
        text = "* **Strengths**: Good work"
        result = ai_client._fix_markdown_formatting(text)
        assert "* **Strengths**: Good work" in result

    def test_empty_string_returns_empty(self, ai_client):
        assert ai_client._fix_markdown_formatting("") == ""

    def test_heading_without_following_text_unchanged(self, ai_client):
        text = "### Structured Summary\n"
        result = ai_client._fix_markdown_formatting(text)
        assert "### Structured Summary" in result

    def test_plain_text_passes_through(self, ai_client):
        text = "This is a plain sentence."
        result = ai_client._fix_markdown_formatting(text)
        assert "This is a plain sentence." in result


# ---------------------------------------------------------------------------
# should_conclude_conversation
# ---------------------------------------------------------------------------

class TestShouldConcludeConversation:

    def test_returns_true_at_turn_limit(self, ai_client):
        with patch("app.services.vertex_ai_client.settings") as mock_settings:
            mock_settings.MAX_TURNS = 5
            ai_client.turn_count = 5
            ai_client.conversation_history = []
            assert ai_client.should_conclude_conversation() is True

    def test_returns_false_below_turn_limit(self, ai_client):
        with patch("app.services.vertex_ai_client.settings") as mock_settings:
            mock_settings.MAX_TURNS = 10
            ai_client.turn_count = 3
            ai_client.conversation_history = []
            assert ai_client.should_conclude_conversation() is False

    def test_returns_true_on_done_phrase(self, ai_client):
        with patch("app.services.vertex_ai_client.settings") as mock_settings:
            mock_settings.MAX_TURNS = 10
            ai_client.turn_count = 2
            ai_client.conversation_history = [
                {"role": "user", "content": "I'm done, that's all"}
            ]
            assert ai_client.should_conclude_conversation() is True

    def test_returns_true_on_finished_phrase(self, ai_client):
        with patch("app.services.vertex_ai_client.settings") as mock_settings:
            mock_settings.MAX_TURNS = 10
            ai_client.turn_count = 2
            ai_client.conversation_history = [
                {"role": "user", "content": "I'm finished"}
            ]
            assert ai_client.should_conclude_conversation() is True

    def test_returns_false_with_no_history(self, ai_client):
        with patch("app.services.vertex_ai_client.settings") as mock_settings:
            mock_settings.MAX_TURNS = 10
            ai_client.turn_count = 0
            ai_client.conversation_history = []
            assert ai_client.should_conclude_conversation() is False

    def test_returns_false_on_normal_message(self, ai_client):
        with patch("app.services.vertex_ai_client.settings") as mock_settings:
            mock_settings.MAX_TURNS = 10
            ai_client.turn_count = 4
            ai_client.conversation_history = [
                {"role": "user", "content": "The student did well in clinic today"}
            ]
            assert ai_client.should_conclude_conversation() is False

    def test_done_phrase_case_insensitive(self, ai_client):
        with patch("app.services.vertex_ai_client.settings") as mock_settings:
            mock_settings.MAX_TURNS = 10
            ai_client.turn_count = 2
            ai_client.conversation_history = [
                {"role": "user", "content": "DONE"}
            ]
            assert ai_client.should_conclude_conversation() is True

    @pytest.mark.parametrize("phrase", ["done", "that's all", "finished", "nothing else", "no more"])
    def test_all_done_phrases(self, ai_client, phrase):
        with patch("app.services.vertex_ai_client.settings") as mock_settings:
            mock_settings.MAX_TURNS = 10
            ai_client.turn_count = 2
            ai_client.conversation_history = [{"role": "user", "content": phrase}]
            assert ai_client.should_conclude_conversation() is True
