"""
Simple markdown to HTML converter for feedback formatting.
Handles the basic markdown patterns used in AI-generated feedback.
"""

import re


def _fix_definition_lists(text: str) -> str:
    """
    Convert Markdown definition-list syntax into bullet format before HTML
    conversion.  LLMs often emit:

        Term
        : Definition

    or the header-only form:

        Strengths
        :
        Competency
        : text

    which should become:

        * **Term**: Definition

    and:

        * **Strengths**:
          * **Competency**: text
    """
    lines = text.split("\n")
    fixed: list[str] = []
    in_sub_block = False
    i = 0
    while i < len(lines):
        current = lines[i]
        next_line = lines[i + 1] if i + 1 < len(lines) else None
        stripped = current.strip()

        # Pass through headings and already-formatted bullets/indented lines
        if (
            current.startswith("#")
            or current.startswith("*")
            or current.startswith(" ")
            or current.startswith("-")
        ):
            if current.startswith("* ") and not current.rstrip().endswith(":"):
                in_sub_block = False
            fixed.append(current)
            i += 1
            continue

        # Blank lines RESET sub-block state and pass through
        if not stripped:
            in_sub_block = False
            fixed.append(current)
            i += 1
            continue

        if next_line is not None and next_line.startswith(": ") and stripped:
            # "Term\n: definition" → bullet (possibly indented)
            definition = next_line[2:]
            if in_sub_block:
                fixed.append(f"  * **{stripped}**: {definition}")
                # Stay in sub-block — next sibling is also a sub-bullet
            else:
                fixed.append(f"* **{stripped}**: {definition}")
            i += 2
        elif next_line is not None and next_line.strip() == ":" and stripped:
            # "Term\n:" → header-only bullet; following items become sub-bullets
            fixed.append(f"* **{stripped}**:")
            in_sub_block = True
            i += 2
        else:
            in_sub_block = False
            fixed.append(current)
            i += 1

    return "\n".join(fixed)


def markdown_to_html(text: str) -> str:
    """
    Convert simple markdown to HTML.

    Supports:
    - ### / ## / # headings
    - **bold** -> <strong>bold</strong>
    - * or - bullet lists (top-level and indented sub-bullets)
    - Definition-list syntax (Term\\n: text) auto-corrected to bullets
    - Blank lines for spacing

    Args:
        text: Markdown text

    Returns:
        HTML text
    """
    if not text:
        return ""

    # Fix definition-list syntax before any other processing
    text = _fix_definition_lists(text)

    # Convert **bold** to <strong>bold</strong>
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)

    lines = text.split('\n')
    html_lines = []
    list_stack: list[str] = []  # stack of 'ul' entries for nesting

    def close_lists_to_depth(depth: int):
        """Close open list tags until the stack is at `depth` levels."""
        while len(list_stack) > depth:
            html_lines.append('</ul>')
            list_stack.pop()

    def open_list_to_depth(depth: int):
        """Open list tags until the stack reaches `depth` levels."""
        while len(list_stack) < depth:
            html_lines.append('<ul>')
            list_stack.append('ul')

    for line in lines:
        stripped = line.strip()

        # --- Headings ---
        heading_match = re.match(r'^(#{1,3})\s+(.*)', line)
        if heading_match:
            close_lists_to_depth(0)
            level = len(heading_match.group(1))
            heading_text = heading_match.group(2)
            html_lines.append(f'<h{level}>{heading_text}</h{level}>')
            continue

        # --- Indented sub-bullet (2+ spaces or tab before * / -)  ---
        indented_bullet = re.match(r'^[ \t]{2,}[*\-]\s+(.*)', line)
        if indented_bullet:
            open_list_to_depth(2)
            html_lines.append(f'<li>{indented_bullet.group(1)}</li>')
            continue

        # --- Top-level bullet ---
        if stripped.startswith('* ') or stripped.startswith('- '):
            close_lists_to_depth(1)
            open_list_to_depth(1)
            item_text = stripped[2:]
            html_lines.append(f'<li>{item_text}</li>')
            continue

        # --- Everything else ---
        close_lists_to_depth(0)

        if stripped:
            html_lines.append(f'<p>{line}</p>')
        # Blank lines are swallowed (block spacing comes from CSS)

    close_lists_to_depth(0)

    return '\n'.join(html_lines)
