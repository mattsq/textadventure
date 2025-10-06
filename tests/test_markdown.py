from __future__ import annotations

from textadventure.markdown import (
    HIGH_CONTRAST_PALETTE,
    SCREEN_READER_PALETTE,
    get_markdown_palette,
    render_markdown,
    set_markdown_palette,
)


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


def test_render_markdown_supports_high_contrast_palette() -> None:
    previous = get_markdown_palette()
    try:
        set_markdown_palette(HIGH_CONTRAST_PALETTE)
        text = """# Heading\n\n- Item"""
        result = render_markdown(text)

        assert "\033[97mHeading\033[0m" in result
        assert "* Item" in result
    finally:
        set_markdown_palette(previous)


def test_render_markdown_supports_screen_reader_palette() -> None:
    previous = get_markdown_palette()
    try:
        set_markdown_palette(SCREEN_READER_PALETTE)
        text = """# Heading\n\n- Item"""
        result = render_markdown(text)

        assert "\033[" not in result
        assert "- Item" in result
        assert SCREEN_READER_PALETTE.screen_reader_mode is True
    finally:
        set_markdown_palette(previous)
