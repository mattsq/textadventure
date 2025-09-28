"""Smoke tests for the command-line interface loop."""

from __future__ import annotations

from collections.abc import Iterator

import builtins

from main import run_cli
from textadventure import WorldState
from textadventure.scripted_story_engine import ScriptedStoryEngine
from textadventure.story_engine import StoryEngine, StoryEvent

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
