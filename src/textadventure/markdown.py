"""Helpers for rendering Markdown-formatted narration to ANSI text."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Mapping


@dataclass(frozen=True)
class MarkdownPalette:
    """ANSI styling applied when rendering Markdown text for the CLI."""

    reset: str = "\033[0m"
    bold: str = "\033[1m"
    italic: str = "\033[3m"
    underline: str = "\033[4m"
    faint: str = "\033[2m"
    code: str = "\033[38;5;214m"
    heading_colours: Mapping[int, str] = field(
        default_factory=lambda: {1: "\033[95m", 2: "\033[94m", 3: "\033[92m"}
    )
    bullet_symbol: str = "•"


DEFAULT_PALETTE = MarkdownPalette()
"""Palette mirroring the original CLI colours."""

HIGH_CONTRAST_PALETTE = MarkdownPalette(
    bold="\033[1m",
    italic="\033[3m",
    underline="\033[4m",
    faint="\033[1m",
    code="\033[97;44m",
    heading_colours={1: "\033[97m", 2: "\033[93m", 3: "\033[96m"},
    bullet_symbol="*",
)
"""Palette tuned for brighter, higher-contrast output."""

_ACTIVE_PALETTE: MarkdownPalette = DEFAULT_PALETTE


def set_markdown_palette(palette: MarkdownPalette) -> None:
    """Set the global palette used by :func:`render_markdown`."""

    global _ACTIVE_PALETTE
    _ACTIVE_PALETTE = palette


def get_markdown_palette() -> MarkdownPalette:
    """Return the palette currently used by :func:`render_markdown`."""

    return _ACTIVE_PALETTE


ORDERED_LIST_PATTERN = re.compile(r"^(\d+)[.)]\s+(.*)")
LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
BOLD_PATTERN = re.compile(r"(\*\*|__)(.+?)\1")
ITALIC_STAR_PATTERN = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
ITALIC_UNDERSCORE_PATTERN = re.compile(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)")
CODE_PATTERN = re.compile(r"`([^`]+)`")
ESCAPED_CHAR_PATTERN = re.compile(r"\\([*_`\\])")


def _strip_ansi_length(text: str) -> int:
    """Return the printable length of ``text`` ignoring ANSI sequences."""

    # ANSI escape codes follow ``\x1b[`` and end with ``m`` for the styles we emit.
    return len(re.sub(r"\x1b\[[0-9;]*m", "", text))


def _restore_escapes(text: str, escapes: Iterable[tuple[str, str]]) -> str:
    """Replace temporary escape placeholders with their literal characters."""

    for placeholder, original in escapes:
        text = text.replace(placeholder, original)
    return text


def _apply_inline_styles(text: str, palette: MarkdownPalette) -> str:
    """Apply inline Markdown formatting (bold, italics, code, links)."""

    escapes: list[tuple[str, str]] = []

    def _replace_escape(match: re.Match[str]) -> str:
        placeholder = f"\uffff{len(escapes)}\uffff"
        escapes.append((placeholder, match.group(1)))
        return placeholder

    text = ESCAPED_CHAR_PATTERN.sub(_replace_escape, text)

    def _replace_code(match: re.Match[str]) -> str:
        return f"{palette.code}{match.group(1)}{palette.reset}"

    text = CODE_PATTERN.sub(_replace_code, text)

    def _replace_bold(match: re.Match[str]) -> str:
        return f"{palette.bold}{match.group(2)}{palette.reset}"

    text = BOLD_PATTERN.sub(_replace_bold, text)

    def _replace_italic(match: re.Match[str]) -> str:
        return f"{palette.italic}{match.group(1)}{palette.reset}"

    text = ITALIC_STAR_PATTERN.sub(_replace_italic, text)
    text = ITALIC_UNDERSCORE_PATTERN.sub(_replace_italic, text)

    def _replace_link(match: re.Match[str]) -> str:
        label = match.group(1)
        url = match.group(2)
        styled_label = f"{palette.underline}{label}{palette.reset}"
        return f"{styled_label} ({url})"

    text = LINK_PATTERN.sub(_replace_link, text)

    return _restore_escapes(text, escapes)


def render_markdown(text: str, *, palette: MarkdownPalette | None = None) -> str:
    """Render a Markdown string to ANSI-coloured text suitable for the CLI."""

    active_palette = palette or _ACTIVE_PALETTE
    lines = text.splitlines()
    rendered: list[str] = []

    for raw_line in lines:
        if not raw_line.strip():
            rendered.append("")
            continue

        stripped = raw_line.lstrip()
        indent = " " * (len(raw_line) - len(stripped))

        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            content = stripped[level:].strip()
            inline = _apply_inline_styles(content, active_palette)
            colour = active_palette.heading_colours.get(level, active_palette.bold)
            heading_text = f"{colour}{inline}{active_palette.reset}"
            rendered.append(f"{indent}{heading_text}")
            underline_char = "=" if level == 1 else "-" if level == 2 else "~"
            underline = underline_char * max(_strip_ansi_length(inline), 1)
            rendered.append(f"{indent}{underline}")
            continue

        if stripped.startswith("> "):
            content = stripped[2:].strip()
            inline = _apply_inline_styles(content, active_palette)
            rendered.append(
                f"{indent}{active_palette.faint}> {inline}{active_palette.reset}"
            )
            continue

        if stripped.startswith(("- ", "* ", "+ ")):
            content = stripped[2:].strip()
            inline = _apply_inline_styles(content, active_palette)
            rendered.append(f"{indent}{active_palette.bullet_symbol} {inline}")
            continue

        ordered = ORDERED_LIST_PATTERN.match(stripped)
        if ordered:
            index, content = ordered.groups()
            inline = _apply_inline_styles(content.strip(), active_palette)
            rendered.append(f"{indent}{index}. {inline}")
            continue

        rendered.append(f"{indent}{_apply_inline_styles(stripped, active_palette)}")

    return "\n".join(rendered)


__all__ = [
    "MarkdownPalette",
    "DEFAULT_PALETTE",
    "HIGH_CONTRAST_PALETTE",
    "get_markdown_palette",
    "render_markdown",
    "set_markdown_palette",
]
