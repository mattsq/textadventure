"""Smoke tests for the command-line interface loop."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from io import StringIO
from pathlib import Path

import builtins

from main import TranscriptLogger, run_cli
from textadventure import InMemorySessionStore, SessionSnapshot, WorldState
from textadventure.multi_agent import (
    Agent,
    AgentTrigger,
    AgentTurnResult,
    MultiAgentCoordinator,
)
from textadventure.scripted_story_engine import ScriptedStoryEngine
from textadventure.story_engine import StoryChoice, StoryEngine, StoryEvent

import pytest


class _IteratorInput:
    """Callable helper that returns successive values from an iterator."""

    def __init__(self, values: Iterator[str]) -> None:
        self._values = values

    def __call__(self, prompt: str = "") -> str:  # pragma: no cover - trivial wrapper
        del prompt
        return next(self._values)


class _EndingEngine(StoryEngine):
    """Story engine that immediately returns a terminal event."""

    def __init__(self) -> None:
        self.calls: list[tuple[str | None, str]] = []

    def propose_event(
        self,
        world_state: WorldState,
        *,
        player_input: str | None = None,
    ) -> StoryEvent:
        self.calls.append((player_input, world_state.location))
        return StoryEvent(narration="The adventure ends before it begins.")


class _SequencedAgent(Agent):
    """Agent that replays a scripted sequence of turn results."""

    def __init__(self, name: str, results: Sequence[AgentTurnResult]) -> None:
        self.name = name
        self._results = list(results)

    def propose_event(
        self,
        world_state: WorldState,
        *,
        trigger: AgentTrigger,
    ) -> AgentTurnResult:
        del world_state, trigger
        if not self._results:
            raise AssertionError(
                f"no scripted result available for agent {self.name!r}"
            )
        return self._results.pop(0)


def test_run_cli_handles_basic_command_sequence(monkeypatch, capsys) -> None:
    """Verify that the CLI processes commands and updates memory."""

    engine = ScriptedStoryEngine()
    world = WorldState()

    inputs = iter(["look", "inventory", "quit"])
    monkeypatch.setattr(builtins, "input", _IteratorInput(inputs))

    run_cli(engine, world)

    captured = capsys.readouterr().out
    assert "Welcome to the Text Adventure prototype!" in captured
    assert "Sunlight filters through tall trees" in captured
    assert "You pause and listen to the rustling leaves." in captured
    assert "You pat your pockets but find nothing of note." in captured
    assert "Thanks for playing!" in captured

    assert world.recent_actions() == ("look", "inventory")
    assert world.location == "starting-area"


def test_run_cli_stops_when_event_has_no_choices(monkeypatch, capsys) -> None:
    """Ensure the loop exits when the story engine provides no choices."""

    engine = _EndingEngine()
    world = WorldState()

    monkeypatch.setattr(
        builtins,
        "input",
        lambda prompt="": pytest.fail("input should not be requested"),
    )

    run_cli(engine, world)

    captured = capsys.readouterr().out
    assert "The adventure ends before it begins." in captured
    assert "The story has reached a natural stopping point." in captured

    assert engine.calls == [(None, "starting-area")]
    assert world.recent_actions() == ()


def test_run_cli_supports_saving_and_loading(monkeypatch, capsys) -> None:
    """Ensure the CLI can persist and restore sessions through commands."""

    engine = ScriptedStoryEngine()
    world = WorldState()
    store = InMemorySessionStore()

    inputs = iter(["save demo", "explore", "save demo", "load demo", "quit"])
    monkeypatch.setattr(builtins, "input", _IteratorInput(inputs))

    run_cli(engine, world, session_store=store)

    captured = capsys.readouterr().out
    assert "Saved session 'demo'." in captured
    assert "Loaded session 'demo'." in captured

    snapshot = store.load("demo")
    assert snapshot.world_state.location == "old-gate"
    assert world.location == "old-gate"
    assert world.recent_actions() == ("explore",)


def test_run_cli_informs_when_saving_unavailable(monkeypatch, capsys) -> None:
    """Saving without a configured session store should produce guidance."""

    engine = ScriptedStoryEngine()
    world = WorldState()

    inputs = iter(["save test", "quit"])
    monkeypatch.setattr(builtins, "input", _IteratorInput(inputs))

    run_cli(engine, world)

    captured = capsys.readouterr().out
    assert "Saving is unavailable" in captured
    assert "Saved session" not in captured
    assert world.recent_actions() == ()


def test_run_cli_autoloads_session(monkeypatch, capsys) -> None:
    """Providing autoload details should restore the world before the loop."""

    engine = ScriptedStoryEngine()
    world = WorldState()
    store = InMemorySessionStore()

    world.move_to("old-gate")
    world.remember_action("explore")
    snapshot = SessionSnapshot.capture(world)
    store.save("resume", snapshot)

    # Reset world to confirm autoload applies snapshot
    world = WorldState()

    inputs = iter(["quit"])
    monkeypatch.setattr(builtins, "input", _IteratorInput(inputs))

    run_cli(engine, world, session_store=store, autoload_session="resume")

    captured = capsys.readouterr().out
    assert "Loaded session 'resume'." in captured
    assert world.location == "old-gate"
    assert world.recent_actions() == ("explore",)


def test_status_command_reports_world_and_queue_details(monkeypatch, capsys) -> None:
    """The debug status command should expose inventory, queue, and saves."""

    world = WorldState()
    world.add_item("lantern")

    store = InMemorySessionStore()
    store.save("checkpoint", SessionSnapshot.capture(world))

    primary_results = (
        AgentTurnResult(
            event=StoryEvent(
                narration="Primary opens the scene.",
                choices=(StoryChoice("wait", "Wait for a moment."),),
            ),
            messages=(
                AgentTrigger(
                    kind="alert",
                    metadata={"target": "scout", "note": "prepare"},
                ),
            ),
        ),
        AgentTurnResult(
            event=StoryEvent(
                narration="Primary continues the tale.",
                choices=(StoryChoice("wait", "Wait for a moment."),),
            ),
        ),
    )

    scout_results = (
        AgentTurnResult(event=StoryEvent("Scout echoes the call.")),
        AgentTurnResult(event=StoryEvent("Scout follows up.")),
    )

    coordinator = MultiAgentCoordinator(
        _SequencedAgent("narrator", primary_results),
        secondary_agents=[_SequencedAgent("scout", scout_results)],
    )

    inputs = iter(["status", "quit"])
    monkeypatch.setattr(builtins, "input", _IteratorInput(inputs))

    run_cli(coordinator, world, session_store=store)

    captured = capsys.readouterr().out
    assert "=== Adventure Status ===" in captured
    assert "Location: starting-area" in captured
    assert "Inventory: lantern" in captured
    assert "Queued agent messages:" in captured
    assert (
        "from narrator (kind=alert, metadata={note=prepare, target=scout})" in captured
    )
    assert "Pending saves: checkpoint" in captured


def test_help_command_offers_contextual_guidance(monkeypatch, capsys) -> None:
    """The help command should surface both general and targeted guidance."""

    engine = ScriptedStoryEngine()
    world = WorldState()

    inputs = iter(["help", "help explore", "help save", "help unknown", "quit"])
    monkeypatch.setattr(builtins, "input", _IteratorInput(inputs))

    run_cli(engine, world)

    output = capsys.readouterr().out
    assert "=== Help ===" in output
    assert "Story choices:" in output
    assert "explore - Head toward the mossy gate." in output
    assert (
        "save <session-id> - Unavailable: session persistence is disabled for this session."
        in output
    )
    assert "=== Help: explore ===" in output
    assert "This choice is currently available: Head toward the mossy gate." in output
    assert "=== Help: save <session-id> ===" in output
    assert "Unavailable: session persistence is disabled for this session." in output
    assert (
        "No help is available for 'unknown'. Showing general guidance instead."
        in output
    )


def test_transcript_logger_captures_inputs_and_events(monkeypatch) -> None:
    """A transcript logger should record narration, metadata, and inputs."""

    engine = ScriptedStoryEngine()
    world = WorldState()

    inputs = iter(["look", "quit"])
    monkeypatch.setattr(builtins, "input", _IteratorInput(inputs))

    buffer = StringIO()
    logger = TranscriptLogger(buffer)

    run_cli(engine, world, transcript_logger=logger)

    log = buffer.getvalue()
    assert "=== Turn 1 ===" in log
    assert "Narration:" in log
    assert "Metadata: (none)" in log
    assert "Player input: look" in log
    assert "Player input: quit" in log


def test_cli_walkthrough_matches_golden(monkeypatch, capsys) -> None:
    """The CLI demo walkthrough should match the curated golden transcript."""

    engine = ScriptedStoryEngine()
    world = WorldState()

    inputs = iter(
        [
            "camp",
            "search",
            "return",
            "lookout",
            "train",
            "return",
            "explore",
            "inspect",
            "enter",
            "hall",
            "excavate",
            "crypt",
            "glean",
            "return",
            "return",
            "archives",
            "salvage",
            "study",
            "return",
            "stair",
            "ascend",
            "workshop",
            "scavenge",
            "craft",
            "return",
            "observatory",
            "activate",
            "advance",
            "stabilize",
            "quit",
        ]
    )
    monkeypatch.setattr(builtins, "input", _IteratorInput(inputs))

    run_cli(engine, world)

    captured = capsys.readouterr().out
    golden_path = (
        Path(__file__).with_name("data").joinpath("golden_cli_walkthrough.txt")
    )
    assert golden_path.is_file(), "Expected golden CLI transcript to be present."
    expected = golden_path.read_text(encoding="utf-8")
    assert captured == expected
