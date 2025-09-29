"""Tests for the adventure analytics helpers."""

from __future__ import annotations

from textadventure.analytics import (
    compute_adventure_complexity,
    compute_adventure_complexity_from_definitions,
    format_complexity_report,
)
from textadventure.scripted_story_engine import load_scenes_from_mapping


_SAMPLE_SCENE_DEFINITIONS = {
    "trail": {
        "description": "A narrow trail leads toward a sealed door.",
        "choices": [
            {"command": "look", "description": "Survey the surroundings."},
            {"command": "take", "description": "Pick up the nearby torch."},
            {"command": "open", "description": "Try opening the door."},
            {"command": "inventory", "description": "Check carried gear."},
        ],
        "transitions": {
            "look": {
                "narration": "You notice etched warnings around the frame.",
                "records": ["inspected-door"],
            },
            "take": {
                "narration": "You grab the torch and brush off loose moss.",
                "item": "torch",
                "records": ["found-torch"],
            },
            "open": {
                "narration": "The door yields, revealing a dark hallway.",
                "target": "hall",
                "requires": ["torch"],
                "failure_narration": "It will not budge without a steady light.",
                "narration_overrides": [
                    {
                        "narration": "Remembering the warnings, you step carefully inside.",
                        "requires_history_any": ["inspected-door"],
                        "records": ["entered-hall"],
                    }
                ],
            },
        },
    },
    "hall": {
        "description": "A vaulted hall echoes with distant chimes.",
        "choices": [
            {"command": "search", "description": "Investigate the alcoves."},
            {"command": "leave", "description": "Retreat back to the trail."},
        ],
        "transitions": {
            "search": {
                "narration": "You recover a resonant shard but the torch gutters out.",
                "consumes": ["torch"],
                "records": ["found-shard"],
            },
            "leave": {
                "narration": "You make a note of the layout before returning.",
                "target": "trail",
            },
        },
    },
}


def test_compute_adventure_complexity() -> None:
    scenes = load_scenes_from_mapping(_SAMPLE_SCENE_DEFINITIONS)
    metrics = compute_adventure_complexity(scenes)

    assert metrics.scene_count == 2
    assert metrics.choice_count == 6
    assert metrics.transition_count == 5
    assert metrics.interactive_choice_count == 5
    assert metrics.commands_without_transitions == 1
    assert metrics.max_choices_in_scene == 4
    assert metrics.max_transitions_in_scene == 3
    assert metrics.terminal_transition_count == 3
    assert metrics.gated_transition_count == 1
    assert metrics.conditional_transition_count == 1
    assert metrics.item_reward_count == 1
    assert metrics.unique_items_awarded == ("torch",)
    assert metrics.unique_items_consumed == ("torch",)
    assert metrics.unique_history_records == (
        "entered-hall",
        "found-shard",
        "found-torch",
        "inspected-door",
    )


def test_compute_from_definitions_matches_direct_metrics() -> None:
    metrics_from_definitions = compute_adventure_complexity_from_definitions(
        _SAMPLE_SCENE_DEFINITIONS
    )
    scenes = load_scenes_from_mapping(_SAMPLE_SCENE_DEFINITIONS)
    direct_metrics = compute_adventure_complexity(scenes)

    assert metrics_from_definitions == direct_metrics


def test_format_complexity_report_includes_key_details() -> None:
    scenes = load_scenes_from_mapping(_SAMPLE_SCENE_DEFINITIONS)
    metrics = compute_adventure_complexity(scenes)
    report = format_complexity_report(metrics)

    assert "Adventure Complexity Metrics" in report
    assert "Scenes: 2" in report
    assert "Choices: 6" in report
    assert "Unique items awarded: torch" in report
    assert "Unique history records: entered-hall" in report
