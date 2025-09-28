"""Tests for the lightweight memory utilities."""

from textadventure.memory import MemoryLog


def test_remember_normalises_fields() -> None:
    log = MemoryLog()
    entry = log.remember("Action", "  Open the Door  ", tags=["Door", "door"])

    assert entry.kind == "action"
    assert entry.content == "Open the Door"
    assert entry.tags == ("door",)
    assert log.recent() == (entry,)


def test_recent_filters_by_kind_and_limit() -> None:
    log = MemoryLog()
    log.remember("action", "Open door")
    log.remember("observation", "You see a hallway")
    log.remember("action", "Step inside")

    actions = log.recent(kind="action", limit=2)

    assert [entry.content for entry in actions] == ["Open door", "Step inside"]


def test_recent_with_zero_limit_returns_empty() -> None:
    log = MemoryLog()
    log.remember("action", "Knock")

    assert log.recent(limit=0) == ()


def test_find_by_tag_matches_case_insensitively() -> None:
    log = MemoryLog()
    first = log.remember("action", "Inspect the altar", tags=["clue"])
    log.remember("action", "Look around", tags=["scenery"])

    matches = log.find_by_tag("Clue")

    assert matches == (first,)
