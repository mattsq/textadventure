"""Tests for the adventure analytics helpers."""

from __future__ import annotations

import pytest

from textadventure.analytics import (
    AdventureReachabilityReport,
    compute_adventure_complexity,
    compute_adventure_complexity_from_definitions,
    compute_adventure_content_distribution,
    compute_adventure_content_distribution_from_definitions,
    compute_scene_reachability,
    compute_scene_reachability_from_definitions,
    format_complexity_report,
    format_content_distribution_report,
    format_reachability_report,
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


_REACHABILITY_SCENE_DEFINITIONS = {
    "starting-area": {
        "description": "A clearing with paths leading deeper into the woods.",
        "choices": [
            {"command": "wait", "description": "Listen to the forest."},
            {"command": "forward", "description": "Follow the stone-lined path."},
        ],
        "transitions": {
            "wait": {
                "narration": "The breeze carries faint chimes from ahead.",
            },
            "forward": {
                "narration": "You stride toward the sound of the chimes.",
                "target": "crossroads",
            },
        },
    },
    "crossroads": {
        "description": "Three archways frame diverging corridors.",
        "choices": [
            {"command": "left", "description": "Ascend the mossy stairs."},
            {"command": "back", "description": "Return to the clearing."},
        ],
        "transitions": {
            "left": {
                "narration": "You climb toward a wind-swept overlook.",
                "target": "overlook",
            },
            "back": {
                "narration": "You retrace your steps to the clearing.",
                "target": "starting-area",
            },
        },
    },
    "overlook": {
        "description": "An open ledge reveals the valley below.",
        "choices": [
            {"command": "return", "description": "Head back to the crossroads."},
        ],
        "transitions": {
            "return": {
                "narration": "You descend the stairs to the crossroads.",
                "target": "crossroads",
            }
        },
    },
    "isolated-sanctum": {
        "description": "A sealed sanctum untouched by visitors.",
        "choices": [
            {"command": "ponder", "description": "Meditate in solitude."},
        ],
        "transitions": {
            "ponder": {
                "narration": "The silence remains undisturbed.",
            }
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


def test_compute_content_distribution() -> None:
    scenes = load_scenes_from_mapping(_SAMPLE_SCENE_DEFINITIONS)
    distribution = compute_adventure_content_distribution(scenes)

    scene_summary = distribution.scene_descriptions
    assert scene_summary.total_entries == 2
    assert scene_summary.total_words == 15
    assert scene_summary.max_words == 8
    assert scene_summary.average_words == pytest.approx(7.5)

    choice_summary = distribution.choice_descriptions
    assert choice_summary.total_entries == 6
    assert choice_summary.total_words == 23
    assert choice_summary.min_words == 3
    assert choice_summary.max_words == 5
    assert choice_summary.average_characters == pytest.approx(23.1666, rel=1e-4)

    transition_summary = distribution.transition_narrations
    assert transition_summary.total_entries == 5
    assert transition_summary.total_words == 42
    assert transition_summary.max_words == 10

    failure_summary = distribution.failure_narrations
    assert failure_summary.total_entries == 1
    assert failure_summary.total_words == 8
    assert failure_summary.average_characters == pytest.approx(41.0)

    conditional_summary = distribution.conditional_narrations
    assert conditional_summary.total_entries == 1
    assert conditional_summary.total_words == 7
    assert conditional_summary.total_characters == 52


def test_content_distribution_from_definitions_matches_direct() -> None:
    direct = compute_adventure_content_distribution(
        load_scenes_from_mapping(_SAMPLE_SCENE_DEFINITIONS)
    )
    via_definitions = compute_adventure_content_distribution_from_definitions(
        _SAMPLE_SCENE_DEFINITIONS
    )

    assert via_definitions == direct


def test_format_content_distribution_report_highlights_sections() -> None:
    distribution = compute_adventure_content_distribution(
        load_scenes_from_mapping(_SAMPLE_SCENE_DEFINITIONS)
    )
    report = format_content_distribution_report(distribution)

    assert "Adventure Content Distribution" in report
    assert "Scene descriptions" in report
    assert "Choice descriptions" in report
    assert "Transition narrations" in report


def test_compute_scene_reachability_identifies_unreachable_scene() -> None:
    scenes = load_scenes_from_mapping(_REACHABILITY_SCENE_DEFINITIONS)
    report = compute_scene_reachability(scenes)

    assert report.start_scene == "starting-area"
    assert report.reachable_count == 3
    assert report.unreachable_scenes == ("isolated-sanctum",)
    assert set(report.reachable_scenes) == {
        "starting-area",
        "crossroads",
        "overlook",
    }
    assert not report.fully_reachable


def test_compute_scene_reachability_from_definitions_matches_direct() -> None:
    direct = compute_scene_reachability(
        load_scenes_from_mapping(_REACHABILITY_SCENE_DEFINITIONS)
    )
    via_definitions = compute_scene_reachability_from_definitions(
        _REACHABILITY_SCENE_DEFINITIONS
    )

    assert via_definitions == AdventureReachabilityReport(
        start_scene="starting-area",
        reachable_scenes=direct.reachable_scenes,
        unreachable_scenes=direct.unreachable_scenes,
    )


def test_format_reachability_report_lists_unreachable_scenes() -> None:
    report = compute_scene_reachability_from_definitions(
        _REACHABILITY_SCENE_DEFINITIONS
    )
    formatted = format_reachability_report(report)

    assert "Adventure Reachability" in formatted
    assert "Reachable scenes: 3 / 4" in formatted
    assert "Unreachable scenes detected" in formatted
    assert "isolated-sanctum" in formatted


def test_compute_scene_reachability_raises_for_unknown_start() -> None:
    scenes = load_scenes_from_mapping(_REACHABILITY_SCENE_DEFINITIONS)

    with pytest.raises(ValueError):
        compute_scene_reachability(scenes, start_scene="missing")
