import json
from typing import TYPE_CHECKING

import pytest

from textadventure import LLMStoryAgent
from textadventure.memory import MemoryRequest
from textadventure.multi_agent import AgentTrigger
from textadventure.story_engine import StoryChoice, StoryEvent
from textadventure.world_state import WorldState

if TYPE_CHECKING:  # pragma: no cover - typing helper
    from tests.conftest import MockLLMClient


def _make_trigger() -> AgentTrigger:
    return AgentTrigger(
        kind="story-event",
        player_input="inspect statue",
        source_event=StoryEvent(
            narration="The statue looms over you.",
            choices=(
                StoryChoice("touch", "Touch the statue"),
                StoryChoice("back", "Back away slowly"),
            ),
        ),
    )


def test_llm_story_agent_builds_prompt_and_parses_response(
    mock_llm_client: "MockLLMClient",
) -> None:
    world = WorldState()
    world.move_to("mysterious-cavern")
    world.add_item("lantern")
    world.record_event("Entered the cavern")
    world.record_event("Heard distant whispers")
    world.remember_action("inspect statue")
    world.remember_observation("A chill settles in the air")

    response_payload = {
        "narration": "A hush falls over the cavern as the statue awakens.",
        "choices": [
            {"command": "wait", "description": "Wait to see what happens."},
            {"command": "run", "description": "Run for the exit."},
        ],
        "metadata": {"tone": "ominous"},
    }
    mock_llm_client.queue_response(
        json.dumps(response_payload), metadata={"model": "mock-gpt"}
    )

    agent = LLMStoryAgent(
        name="oracle",
        llm_client=mock_llm_client,
        history_limit=1,
        memory_limit=1,
    )

    result = agent.propose_event(world, trigger=_make_trigger())

    assert result.event is not None
    event = result.event
    assert event.narration == response_payload["narration"]
    assert [choice.command for choice in event.choices] == ["wait", "run"]
    metadata = dict(event.metadata)
    assert metadata["tone"] == "ominous"
    assert metadata["llm:model"] == "mock-gpt"

    assert len(mock_llm_client.calls) == 1
    system_message, user_message = mock_llm_client.calls[0]
    assert system_message.role == "system"
    assert "Respond with JSON" in system_message.content
    assert "Trigger kind: story-event" in user_message.content
    assert "Player input: inspect statue" in user_message.content
    assert "touch: Touch the statue" in user_message.content
    assert "Current location: mysterious-cavern" in user_message.content
    assert "Inventory: lantern" in user_message.content
    assert "Recent history:\n- Heard distant whispers" in user_message.content
    assert "Recent player actions:\n- inspect statue" in user_message.content
    assert "Recent observations:\n- A chill settles in the air" in user_message.content
    assert "Entered the cavern" not in user_message.content


def test_llm_story_agent_requires_json_response(
    mock_llm_client: "MockLLMClient",
) -> None:
    mock_llm_client.queue_response("Not JSON at all")

    agent = LLMStoryAgent(name="oracle", llm_client=mock_llm_client)

    with pytest.raises(ValueError, match="expected JSON content"):
        agent.propose_event(WorldState(), trigger=_make_trigger())


def test_llm_story_agent_respects_memory_request_override(
    mock_llm_client: "MockLLMClient",
) -> None:
    world = WorldState()
    for command in ("search", "inspect", "touch", "retreat"):
        world.remember_action(command)
    for description in ("Dust swirls in the air", "A glyph glows softly"):
        world.remember_observation(description)

    mock_llm_client.queue_response(json.dumps({"narration": "Done."}))

    agent = LLMStoryAgent(
        name="oracle",
        llm_client=mock_llm_client,
        memory_limit=1,
    )

    trigger = AgentTrigger(
        kind="story-event",
        player_input="inspect statue",
        source_event=_make_trigger().source_event,
        memory_request=MemoryRequest(action_limit=3, observation_limit=0),
    )

    agent.propose_event(world, trigger=trigger)

    _, user_message = mock_llm_client.calls[0]
    assert (
        "Recent player actions:\n- inspect\n- touch\n- retreat"
        in user_message.content
    )
    assert "search" not in user_message.content
    assert "Recent observations: (none)" in user_message.content
    assert "A glyph glows softly" not in user_message.content
