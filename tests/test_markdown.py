"""
Unit tests for markdown_to_html and _fix_definition_lists.
Pure functions — no mocking required.
"""

import pytest
from app.utils.markdown import markdown_to_html, _fix_definition_lists


class TestFixDefinitionLists:

    def test_simple_term_definition(self):
        text = "Context of evaluation\n: Outpatient clinic"
        result = _fix_definition_lists(text)
        assert "* **Context of evaluation**: Outpatient clinic" in result

    def test_header_only_form_starts_sub_block(self):
        text = "Strengths\n:"
        result = _fix_definition_lists(text)
        assert "* **Strengths**:" in result

    def test_sub_bullets_under_header(self):
        text = "Strengths\n:\nPatient Care\n: Good history taking"
        result = _fix_definition_lists(text)
        assert "* **Strengths**:" in result
        assert "  * **Patient Care**: Good history taking" in result

    def test_multiple_sub_bullets(self):
        text = "Strengths\n:\nPatient Care\n: Good\nCommunication\n: Clear"
        result = _fix_definition_lists(text)
        assert "  * **Patient Care**: Good" in result
        assert "  * **Communication**: Clear" in result

    def test_blank_line_resets_sub_block(self):
        # In markdown.py (unlike vertex_ai_client), blank lines DO reset the sub-block
        text = "Strengths\n:\nPatient Care\n: Good\n\nAreas for Improvement\n: Presentations"
        result = _fix_definition_lists(text)
        assert "  * **Patient Care**: Good" in result
        # After blank line, next item should be top-level, not indented
        assert "* **Areas for Improvement**: Presentations" in result
        assert "  * **Areas for Improvement**" not in result

    def test_already_formatted_bullet_passes_through(self):
        text = "* **Strengths**: Already formatted"
        result = _fix_definition_lists(text)
        assert text in result

    def test_heading_passes_through(self):
        text = "### Structured Summary"
        result = _fix_definition_lists(text)
        assert "### Structured Summary" in result

    def test_plain_text_passes_through(self):
        text = "Just a plain sentence."
        result = _fix_definition_lists(text)
        assert "Just a plain sentence." in result

    def test_empty_string(self):
        assert _fix_definition_lists("") == ""


class TestMarkdownToHtml:

    def test_empty_returns_empty(self):
        assert markdown_to_html("") == ""

    def test_none_equivalent(self):
        assert markdown_to_html(None) == ""

    def test_h3_heading(self):
        result = markdown_to_html("### Structured Summary")
        assert "<h3>Structured Summary</h3>" in result

    def test_h2_heading(self):
        result = markdown_to_html("## Section")
        assert "<h2>Section</h2>" in result

    def test_h1_heading(self):
        result = markdown_to_html("# Title")
        assert "<h1>Title</h1>" in result

    def test_bold_text(self):
        result = markdown_to_html("**bold text**")
        assert "<strong>bold text</strong>" in result

    def test_top_level_bullet_star(self):
        result = markdown_to_html("* Item one")
        assert "<ul>" in result
        assert "<li>Item one</li>" in result

    def test_top_level_bullet_dash(self):
        result = markdown_to_html("- Item one")
        assert "<li>Item one</li>" in result

    def test_multiple_bullets_single_list(self):
        text = "* Item one\n* Item two\n* Item three"
        result = markdown_to_html(text)
        assert result.count("<ul>") == 1
        assert result.count("</ul>") == 1
        assert result.count("<li>") == 3

    def test_indented_sub_bullet(self):
        text = "* **Strengths**:\n  * Sub item"
        result = markdown_to_html(text)
        assert result.count("<ul>") == 2  # outer + inner
        assert "<li>Sub item</li>" in result

    def test_plain_paragraph(self):
        result = markdown_to_html("Just a sentence.")
        assert "<p>Just a sentence.</p>" in result

    def test_blank_lines_not_emitted_as_tags(self):
        result = markdown_to_html("Line one\n\nLine two")
        assert "<p></p>" not in result

    def test_list_closed_before_heading(self):
        text = "* Item\n### Heading"
        result = markdown_to_html(text)
        # </ul> should appear before <h3>
        assert result.index("</ul>") < result.index("<h3>")

    def test_bold_inside_list_item(self):
        result = markdown_to_html("* **Label**: text")
        assert "<strong>Label</strong>" in result
        assert "<li>" in result

    def test_definition_list_converted(self):
        text = "Context of evaluation\n: Outpatient clinic"
        result = markdown_to_html(text)
        assert "<strong>Context of evaluation</strong>" in result
        assert "Outpatient clinic" in result

    def test_full_feedback_structure(self):
        text = (
            "### Structured Summary\n\n"
            "* **Context of evaluation**: Outpatient clinic\n"
            "* **Strengths**:\n"
            "  * **Patient Care**: Excellent\n"
            "* **Areas for Improvement**: Oral presentations\n\n"
            "### Student-Facing Narrative\n\n"
            "You demonstrated excellent clinical skills."
        )
        result = markdown_to_html(text)
        assert "<h3>Structured Summary</h3>" in result
        assert "<h3>Student-Facing Narrative</h3>" in result
        assert "<strong>Patient Care</strong>" in result
        assert "Oral presentations" in result
        assert "<p>" in result
