"""Unit tests for tool abstractions supporting the adventure."""

from __future__ import annotations

import pytest

from textadventure import KnowledgeBaseTool, WorldState


def test_knowledge_base_returns_entry_for_known_topic() -> None:
    tool = KnowledgeBaseTool(entries={"topic": "Detailed lore entry."})
    world = WorldState()

    response = tool.invoke("topic", world_state=world)

    assert response.narration == "Detailed lore entry."
    assert response.metadata["status"] == "ok"
    assert response.metadata["topic"] == "topic"


def test_knowledge_base_prompts_for_topic_when_missing() -> None:
    tool = KnowledgeBaseTool(entries={"topic": "Entry."})

    response = tool.invoke("", world_state=WorldState())

    assert "need a topic" in response.narration.lower()
    assert response.metadata["status"] == "missing_query"


def test_knowledge_base_handles_unknown_topic() -> None:
    tool = KnowledgeBaseTool(entries={"topic": "Entry."})

    response = tool.invoke("unknown", world_state=WorldState())

    assert "no entry" in response.narration.lower()
    assert response.metadata["status"] == "not_found"
    assert response.metadata["topic"] == "unknown"


def test_knowledge_base_requires_entries() -> None:
    with pytest.raises(ValueError):
        KnowledgeBaseTool(entries={})
