from __future__ import annotations

from textadventure.markdown import render_markdown


def test_render_markdown_applies_inline_styles() -> None:
    result = render_markdown("You find **bold** and *italic* plus `code`.")

    assert "\033[1mbold\033[0m" in result
    assert "\033[3mitalic\033[0m" in result
    assert "\033[38;5;214mcode\033[0m" in result


def test_render_markdown_handles_headings_and_lists() -> None:
    text = """# Heading\n\n- First item\n- Second item"""

    result = render_markdown(text)

    assert "Heading" in result
    assert "=" * len("Heading") in result
    assert "• First item" in result
    assert "• Second item" in result
