"""Helpers for rendering Markdown-formatted narration to ANSI text."""

from __future__ import annotations

import re
from typing import Iterable

RESET = "\033[0m"
BOLD = "\033[1m"
ITALIC = "\033[3m"
UNDERLINE = "\033[4m"
FAINT = "\033[2m"
CODE = "\033[38;5;214m"
HEADING_COLOURS = {
    1: "\033[95m",  # magenta
    2: "\033[94m",  # blue
    3: "\033[92m",  # green
}
BULLET_SYMBOL = "•"
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


def _apply_inline_styles(text: str) -> str:
    """Apply inline Markdown formatting (bold, italics, code, links)."""

    escapes: list[tuple[str, str]] = []

    def _replace_escape(match: re.Match[str]) -> str:
        placeholder = f"\uffff{len(escapes)}\uffff"
        escapes.append((placeholder, match.group(1)))
        return placeholder

    text = ESCAPED_CHAR_PATTERN.sub(_replace_escape, text)

    def _replace_code(match: re.Match[str]) -> str:
        return f"{CODE}{match.group(1)}{RESET}"

    text = CODE_PATTERN.sub(_replace_code, text)

    def _replace_bold(match: re.Match[str]) -> str:
        return f"{BOLD}{match.group(2)}{RESET}"

    text = BOLD_PATTERN.sub(_replace_bold, text)

    def _replace_italic(match: re.Match[str]) -> str:
        return f"{ITALIC}{match.group(1)}{RESET}"

    text = ITALIC_STAR_PATTERN.sub(_replace_italic, text)
    text = ITALIC_UNDERSCORE_PATTERN.sub(_replace_italic, text)

    def _replace_link(match: re.Match[str]) -> str:
        label = match.group(1)
        url = match.group(2)
        styled_label = f"{UNDERLINE}{label}{RESET}"
        return f"{styled_label} ({url})"

    text = LINK_PATTERN.sub(_replace_link, text)

    return _restore_escapes(text, escapes)


def render_markdown(text: str) -> str:
    """Render a Markdown string to ANSI-coloured text suitable for the CLI."""

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
            inline = _apply_inline_styles(content)
            colour = HEADING_COLOURS.get(level, BOLD)
            heading_text = f"{colour}{inline}{RESET}"
            rendered.append(f"{indent}{heading_text}")
            underline_char = "=" if level == 1 else "-" if level == 2 else "~"
            underline = underline_char * max(_strip_ansi_length(inline), 1)
            rendered.append(f"{indent}{underline}")
            continue

        if stripped.startswith("> "):
            content = stripped[2:].strip()
            inline = _apply_inline_styles(content)
            rendered.append(f"{indent}{FAINT}> {inline}{RESET}")
            continue

        if stripped.startswith(("- ", "* ", "+ ")):
            content = stripped[2:].strip()
            inline = _apply_inline_styles(content)
            rendered.append(f"{indent}{BULLET_SYMBOL} {inline}")
            continue

        ordered = ORDERED_LIST_PATTERN.match(stripped)
        if ordered:
            index, content = ordered.groups()
            inline = _apply_inline_styles(content.strip())
            rendered.append(f"{indent}{index}. {inline}")
            continue

        rendered.append(f"{indent}{_apply_inline_styles(stripped)}")

    return "\n".join(rendered)


__all__ = ["render_markdown"]
