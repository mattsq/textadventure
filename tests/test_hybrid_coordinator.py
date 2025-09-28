import json
from collections import Counter
from typing import TYPE_CHECKING

from textadventure import LLMStoryAgent, MultiAgentCoordinator, ScriptedStoryAgent
from textadventure.scripted_story_engine import ScriptedStoryEngine
from textadventure.world_state import WorldState

if TYPE_CHECKING:  # pragma: no cover - typing helper
    from collections.abc import Callable, Sequence

    from textadventure.llm import LLMResponse

    from tests.conftest import MockLLMClient

    MockClientFactory = Callable[[Sequence[LLMResponse | str] | None], MockLLMClient]


def test_hybrid_coordinator_merges_scripted_and_llm_agents(
    make_mock_llm_client: "MockClientFactory",  # type: ignore[name-defined]
) -> None:
    llm_client = make_mock_llm_client()

    first_payload = {
        "narration": "A calm voice assures you the gate conceals friendly mysteries.",
        "metadata": {"tone": "hopeful"},
    }
    llm_client.queue_response(
        json.dumps(first_payload),
        metadata={"model": "mock-gpt", "cost": "0"},
    )

    second_payload = {
        "narration": "The voice hints that the glinting key may unlock a hidden door.",
        "choices": [
            {
                "command": "inspect",
                "description": "Follow the hint and inspect the key closely.",
            }
        ],
        "metadata": {"hint": "Inspect the key."},
    }
    llm_client.queue_response(
        json.dumps(second_payload),
        metadata={"model": "mock-gpt", "cost": "1"},
    )

    world = WorldState()
    world.add_item("compass")
    world.record_event("Arrived at the forest trailhead")
    world.remember_action("wake up")
    world.remember_observation("Sunlight warms the clearing")

    scripted_engine = ScriptedStoryEngine()
    coordinator = MultiAgentCoordinator(
        ScriptedStoryAgent("narrator", scripted_engine),
        secondary_agents=[
            LLMStoryAgent(
                name="oracle",
                llm_client=llm_client,
                history_limit=3,
                memory_limit=2,
            )
        ],
    )

    opening_event = coordinator.propose_event(world)
    world.remember_observation(opening_event.narration)

    assert "Sunlight filters through tall trees" in opening_event.narration
    assert first_payload["narration"] in opening_event.narration

    assert opening_event.metadata is not None
    opening_metadata = dict(opening_event.metadata)
    assert opening_metadata["oracle:tone"] == "hopeful"
    assert opening_metadata["oracle:llm:model"] == "mock-gpt"
    assert opening_metadata["oracle:llm:cost"] == "0"

    opening_commands = Counter(choice.command for choice in opening_event.choices)
    assert opening_commands["look"] == 1
    assert opening_commands["explore"] == 1

    first_system, first_user = llm_client.calls[0]
    assert first_system.role == "system"
    assert "Respond with JSON" in first_system.content
    assert "Trigger kind: story-event" in first_user.content
    assert "Current location: starting-area" in first_user.content
    assert "Inventory: compass" in first_user.content
    assert "Recent player actions:\n- wake up" in first_user.content

    world.remember_action("explore")
    second_event = coordinator.propose_event(world, player_input="explore")
    world.remember_observation(second_event.narration)

    assert "You follow the worn path toward the gate." in second_event.narration
    assert second_payload["narration"] in second_event.narration
    assert world.location == "old-gate"

    assert second_event.metadata is not None
    second_metadata = dict(second_event.metadata)
    assert second_metadata["oracle:hint"] == "Inspect the key."
    assert second_metadata["oracle:llm:model"] == "mock-gpt"
    assert second_metadata["oracle:llm:cost"] == "1"

    second_commands = [choice.command for choice in second_event.choices]
    assert second_commands.count("inspect") == 1
    assert set(second_commands) >= {"look", "inspect", "return"}

    second_system, second_user = llm_client.calls[1]
    assert second_system.role == "system"
    assert "Player input: explore" in second_user.content
    assert "Current location: old-gate" in second_user.content
    assert "Recent observations" in second_user.content

