from __future__ import annotations

from typing import Callable

import pytest

from textadventure.api.app import (
    PlaytestSession,
    PlaytestTranscriptEntry,
    replay_playtest_transcript,
)
from textadventure.scripted_story_engine import (
    ScriptedStoryEngine,
    load_scenes_from_mapping,
)
from textadventure.story_engine import StoryEvent


def _build_simple_engine_factory() -> Callable[[], ScriptedStoryEngine]:
    definitions = {
        "starting-area": {
            "description": "A quiet clearing.",
            "choices": [
                {"command": "wait", "description": "Pause and listen."},
            ],
            "transitions": {
                "wait": {
                    "narration": "Time drifts by while the forest hums softly.",
                    "target": "starting-area",
                }
            },
        }
    }

    def _factory() -> ScriptedStoryEngine:
        scenes = load_scenes_from_mapping(definitions)
        return ScriptedStoryEngine(scenes=scenes)

    return _factory


def test_replay_playtest_transcript_matches_recorded_events() -> None:
    engine_factory = _build_simple_engine_factory()
    session = PlaytestSession(engine_factory)

    session.reset()
    session.apply_player_input("wait")

    transcript = session.transcript()
    result = replay_playtest_transcript(transcript, engine_factory=engine_factory)

    assert result.is_successful
    assert len(result.steps) == len(transcript)
    assert all(step.matches for step in result.steps)


def test_replay_playtest_transcript_reports_mismatched_events() -> None:
    engine_factory = _build_simple_engine_factory()
    session = PlaytestSession(engine_factory)

    session.reset()
    session.apply_player_input("wait")

    transcript = list(session.transcript())
    # Tamper with the second recorded event to simulate a regression in narration.
    transcript[1] = PlaytestTranscriptEntry(
        turn=transcript[1].turn,
        player_input=transcript[1].player_input,
        event=StoryEvent(
            narration="An unexpected gale whips through the clearing.",
            choices=transcript[1].event.choices,
            metadata=dict(transcript[1].event.metadata),
        ),
    )

    result = replay_playtest_transcript(
        tuple(transcript), engine_factory=engine_factory
    )

    assert not result.is_successful
    assert len(result.mismatches) == 1
    mismatch = result.mismatches[0]
    assert mismatch.entry.turn == transcript[1].turn
    assert mismatch.actual_event.narration != mismatch.entry.event.narration


def test_replay_playtest_transcript_validates_turn_sequence() -> None:
    engine_factory = _build_simple_engine_factory()
    session = PlaytestSession(engine_factory)

    session.reset()
    transcript = session.transcript()

    bad_transcript = (
        PlaytestTranscriptEntry(
            turn=2,
            player_input=None,
            event=transcript[0].event,
        ),
    )

    with pytest.raises(ValueError):
        replay_playtest_transcript(bad_transcript, engine_factory=engine_factory)


def test_replay_playtest_transcript_requires_initial_event_entry() -> None:
    engine_factory = _build_simple_engine_factory()
    session = PlaytestSession(engine_factory)

    session.reset()
    session.apply_player_input("wait")
    transcript = session.transcript()

    truncated_transcript = (
        PlaytestTranscriptEntry(
            turn=1,
            player_input=transcript[1].player_input,
            event=transcript[1].event,
        ),
    )

    with pytest.raises(ValueError):
        replay_playtest_transcript(truncated_transcript, engine_factory=engine_factory)
