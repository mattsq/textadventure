"""Integration-style tests replaying recorded LLM transcripts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterable, List

import pytest

from textadventure import LLMStoryAgent
from textadventure.multi_agent import AgentTrigger
from textadventure.story_engine import StoryEvent
from textadventure.world_state import WorldState

if TYPE_CHECKING:  # pragma: no cover - typing helper
    from tests.conftest import MockLLMClient


_FIXTURE_PATH = (
    Path(__file__).with_name("data").joinpath("llm_recorded_transcripts.json")
)
_RECORDED_FIXTURES: Dict[str, Any] = json.loads(_FIXTURE_PATH.read_text())


def _build_world(state: Dict[str, Any]) -> WorldState:
    world = WorldState()
    world.move_to(state["location"], record_event=False)
    for item in state.get("inventory", []):
        world.add_item(item, record_event=False)
    world.extend_history(state.get("history", []))
    for action in state.get("actions", []):
        world.remember_action(action)
    for observation in state.get("observations", []):
        world.remember_observation(observation)
    return world


def _queue_responses(client: "MockLLMClient", turns: Iterable[Dict[str, Any]]) -> None:
    for turn in turns:
        payload = json.dumps(turn["response_payload"])
        metadata = turn.get("response_metadata", {})
        client.queue_response(payload, metadata=metadata)


def test_llm_story_agent_replays_recorded_transcript(
    mock_llm_client: "MockLLMClient",
) -> None:
    transcript = _RECORDED_FIXTURES["turns"]
    _queue_responses(mock_llm_client, transcript)

    world = _build_world(_RECORDED_FIXTURES["world"])
    agent = LLMStoryAgent(
        name="oracle",
        llm_client=mock_llm_client,
        history_limit=5,
        memory_limit=5,
    )

    previous_event: StoryEvent | None = None

    for index, turn in enumerate(transcript):
        trigger = AgentTrigger(
            kind="story-event",
            player_input=turn.get("player_input"),
            source_event=previous_event,
        )

        result = agent.propose_event(world, trigger=trigger)
        assert result.event is not None
        event = result.event

        assert event.narration == turn["response_payload"]["narration"]
        assert [choice.command for choice in event.choices] == turn["expected_choices"]

        metadata = dict(event.metadata or {})
        assert metadata == turn["expected_metadata"]

        system_message, user_message = mock_llm_client.calls[index]
        assert system_message.role == "system"
        for snippet in turn["expected_prompt_snippets"]:
            assert snippet in user_message.content

        if turn.get("player_input"):
            world.remember_action(turn["player_input"])
        world.remember_observation(event.narration)
        previous_event = event


def _invalid_payloads() -> List[Dict[str, str]]:
    return list(_RECORDED_FIXTURES.get("invalid_payloads", []))


@pytest.mark.parametrize(
    "payload_record",
    _invalid_payloads(),
    ids=lambda record: record.get("description", "invalid"),
)
def test_llm_story_agent_handles_recorded_invalid_payloads(
    payload_record: Dict[str, str], mock_llm_client: "MockLLMClient"
) -> None:
    mock_llm_client.queue_response(payload_record["payload"])

    agent = LLMStoryAgent(name="oracle", llm_client=mock_llm_client)
    trigger = AgentTrigger(kind="story-event")

    with pytest.raises(ValueError, match=payload_record["error_match"]):
        agent.propose_event(world_state=WorldState(), trigger=trigger)
