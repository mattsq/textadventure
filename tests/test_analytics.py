"""Tests for the adventure analytics helpers."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from textadventure.analytics import (
    AdventureABCollectionDifference,
    AdventureABTestReport,
    AdventureReachabilityReport,
    ItemConsumption,
    ItemFlowDetails,
    ItemFlowReport,
    ItemRequirement,
    ItemSource,
    analyse_item_flow,
    analyse_item_flow_from_definitions,
    assess_adventure_quality,
    assess_adventure_quality_from_definitions,
    compare_adventure_variants,
    compare_adventure_variants_from_definitions,
    compute_adventure_complexity,
    compute_adventure_complexity_from_definitions,
    compute_adventure_content_distribution,
    compute_adventure_content_distribution_from_definitions,
    compute_scene_reachability,
    compute_scene_reachability_from_definitions,
    format_item_flow_report,
    format_ab_test_report,
    format_complexity_report,
    format_content_distribution_report,
    format_quality_report,
    format_reachability_report,
)
from textadventure.scripted_story_engine import load_scenes_from_mapping


@dataclass(frozen=True)
class _StubChoice:
    command: str
    description: str


@dataclass(frozen=True)
class _StubConditionalNarration:
    narration: str
    records: tuple[str, ...] = ()


@dataclass(frozen=True)
class _StubTransition:
    narration: str
    failure_narration: str | None = None
    target: str | None = None
    item: str | None = None
    requires: tuple[str, ...] = ()
    consumes: tuple[str, ...] = ()
    records: tuple[str, ...] = ()
    narration_overrides: tuple[_StubConditionalNarration, ...] = ()


@dataclass(frozen=True)
class _StubScene:
    description: str
    choices: tuple[_StubChoice, ...]
    transitions: dict[str, _StubTransition]


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


_QUALITY_SCENE_DEFINITIONS = {
    "entry": {
        "description": "A threshold between the forest and the ruin.",
        "choices": [
            {"command": "push", "description": "Push the heavy door."},
        ],
        "transitions": {
            "push": {
                "narration": " ",
                "requires": ["iron-key"],
                "narration_overrides": [
                    {"narration": " ", "requires_history_any": ["inspected-door"]}
                ],
            }
        },
    }
}


_QUALITY_SCENES = {
    "empty": _StubScene(
        description=" ",
        choices=(_StubChoice(command="noop", description=""),),
        transitions={
            "noop": _StubTransition(
                narration="",
                requires=("key",),
                failure_narration=" ",
                narration_overrides=(_StubConditionalNarration(narration=" "),),
            )
        },
    ),
    "complete": _StubScene(
        description="A well described scene.",
        choices=(_StubChoice(command="go", description="Proceed forward."),),
        transitions={
            "go": _StubTransition(
                narration="You continue onward.",
                target="empty",
            )
        },
    ),
}


_ITEM_FLOW_SCENE_DEFINITIONS = {
    "forge": {
        "description": "Sparks rain from the ancient anvil.",
        "choices": [
            {"command": "take-hammer", "description": "Take the smith's hammer."},
            {"command": "polish", "description": "Polish the hammer."},
            {"command": "leave", "description": "Step into the vault."},
        ],
        "transitions": {
            "take-hammer": {
                "narration": "You claim the sturdy hammer.",
                "item": "hammer",
            },
            "polish": {
                "narration": "You polish the hammer and place it aside.",
                "consumes": ["hammer"],
            },
            "leave": {
                "narration": "You carry your tools into the vault.",
                "target": "vault",
            },
        },
    },
    "garden": {
        "description": "Fresh herbs thrive beside the walkway.",
        "choices": [
            {"command": "pick-herb", "description": "Gather a handful of herbs."},
            {"command": "rest", "description": "Rest on the stone bench."},
        ],
        "transitions": {
            "pick-herb": {
                "narration": "You pick a fragrant bundle of herbs.",
                "item": "herb",
            },
            "rest": {"narration": "You breathe in the calming scent."},
        },
    },
    "vault": {
        "description": "A heavy golden door blocks the vault.",
        "choices": [
            {"command": "unlock", "description": "Unlock the golden door."},
            {"command": "return", "description": "Return to the garden."},
        ],
        "transitions": {
            "unlock": {
                "narration": "The lock accepts a golden key with a soft click.",
                "requires": ["gold-key"],
            },
            "return": {
                "narration": "You stroll back to the herb garden.",
                "target": "garden",
            },
        },
    },
}


_AB_TEST_BASELINE_DEFINITIONS = {
    "start": {
        "description": "The antechamber is lit by flickering braziers.",
        "choices": [
            {"command": "take-torch", "description": "Lift a torch from the wall."},
            {"command": "proceed", "description": "Advance toward the hall."},
        ],
        "transitions": {
            "take-torch": {
                "narration": "You lift the torch and feel its warmth.",
                "item": "torch",
                "records": ["torch-collected"],
            },
            "proceed": {
                "narration": "You enter the hall cautiously.",
                "target": "hall",
                "requires": ["torch"],
                "failure_narration": "It is too dark to continue without a torch.",
            },
        },
    },
    "hall": {
        "description": "An echoing hall lined with statues.",
        "choices": [
            {"command": "listen", "description": "Listen for distant echoes."},
            {"command": "return", "description": "Retreat to the antechamber."},
        ],
        "transitions": {
            "listen": {
                "narration": "A faint melody drifts from below.",
                "records": ["heard-melody"],
            },
            "return": {
                "narration": "You step back into the antechamber.",
                "target": "start",
            },
        },
    },
}


_AB_TEST_EXPERIMENT_DEFINITIONS = {
    "start": {
        "description": "The antechamber is lit by flickering braziers.",
        "choices": [
            {"command": "take-torch", "description": "Lift a torch from the wall."},
            {"command": "inspect", "description": "Inspect the mosaic for clues."},
            {"command": "proceed", "description": "Advance toward the hall."},
        ],
        "transitions": {
            "take-torch": {
                "narration": "You lift the torch and feel its warmth.",
                "item": "torch",
                "records": ["torch-collected"],
            },
            "inspect": {
                "narration": "Behind the mosaic you uncover a crystal lens.",
                "item": "lens",
                "records": ["found-lens"],
            },
            "proceed": {
                "narration": "The hall's murals shimmer as the lens focuses the light.",
                "target": "hall",
                "requires": ["torch"],
                "failure_narration": "It is too dark to continue without a torch.",
                "narration_overrides": [
                    {
                        "narration": "With the lens in hand you note hidden carvings.",
                        "requires_history_any": ["found-lens"],
                        "records": ["studied-carvings"],
                    }
                ],
            },
        },
    },
    "hall": {
        "description": "An echoing hall lined with statues.",
        "choices": [
            {"command": "listen", "description": "Listen for distant echoes."},
            {"command": "descend", "description": "Descend toward the vault."},
            {"command": "return", "description": "Retreat to the antechamber."},
        ],
        "transitions": {
            "listen": {
                "narration": "A faint melody drifts from below.",
                "records": ["heard-melody"],
            },
            "descend": {
                "narration": "You unlock the stairwell using the lens as a key.",
                "target": "vault",
                "requires": ["lens"],
                "consumes": ["lens"],
                "records": ["vault-opened"],
            },
            "return": {
                "narration": "You step back into the antechamber.",
                "target": "start",
            },
        },
    },
    "vault": {
        "description": "The vault glitters with sigils etched into the walls.",
        "choices": [
            {"command": "claim", "description": "Claim the resonant sigil."},
            {"command": "exit", "description": "Return to the hall."},
        ],
        "transitions": {
            "claim": {
                "narration": "You claim the sigil which hums with potential.",
                "item": "sigil",
                "records": ["claimed-sigil"],
            },
            "exit": {
                "narration": "You ascend back to the hall.",
                "target": "hall",
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


def test_assess_adventure_quality_highlights_issues() -> None:
    report = assess_adventure_quality(_QUALITY_SCENES)

    assert report.has_issues
    assert report.scenes_missing_description == ("empty",)
    assert report.choices_missing_description == (("empty", "noop"),)
    assert report.transitions_missing_narration == (("empty", "noop"),)
    assert report.gated_transitions_missing_failure == (("empty", "noop"),)
    assert report.conditional_overrides_missing_narration == (("empty", "noop", 0),)


def test_assess_adventure_quality_from_definitions_matches_direct() -> None:
    report = assess_adventure_quality_from_definitions(_QUALITY_SCENE_DEFINITIONS)

    assert not report.scenes_missing_description
    assert not report.choices_missing_description
    assert report.transitions_missing_narration == (("entry", "push"),)
    assert report.gated_transitions_missing_failure == (("entry", "push"),)
    assert report.conditional_overrides_missing_narration == (("entry", "push", 0),)


def test_format_quality_report_lists_detected_issues() -> None:
    report = assess_adventure_quality_from_definitions(_QUALITY_SCENE_DEFINITIONS)
    formatted = format_quality_report(report)

    assert "Adventure Quality Assessment" in formatted
    assert "Total issues detected: 3" in formatted
    assert "Scenes missing descriptions" not in formatted
    assert "Conditional overrides missing narration" in formatted


def test_analyse_item_flow_tracks_sources_and_usage() -> None:
    scenes = load_scenes_from_mapping(_ITEM_FLOW_SCENE_DEFINITIONS)
    report = analyse_item_flow(scenes)

    assert isinstance(report, ItemFlowReport)
    details_by_item = {detail.item: detail for detail in report.items}

    hammer = details_by_item["hammer"]
    assert isinstance(hammer, ItemFlowDetails)
    assert hammer.sources == (ItemSource(scene="forge", command="take-hammer"),)
    assert hammer.requirements == ()
    assert hammer.consumptions == (ItemConsumption(scene="forge", command="polish"),)

    herb = details_by_item["herb"]
    assert herb.sources == (ItemSource(scene="garden", command="pick-herb"),)
    assert herb.requirements == ()
    assert herb.consumptions == ()

    gold_key = details_by_item["gold-key"]
    assert gold_key.sources == ()
    assert gold_key.requirements == (ItemRequirement(scene="vault", command="unlock"),)
    assert gold_key.consumptions == ()

    assert report.orphaned_items == ("herb",)
    assert report.items_missing_sources == ("gold-key",)


def test_item_flow_report_classifies_balance_states() -> None:
    report = ItemFlowReport(
        items=(
            ItemFlowDetails(
                item="balanced",
                sources=(ItemSource(scene="forge", command="award"),),
                requirements=(),
                consumptions=(ItemConsumption(scene="forge", command="consume"),),
            ),
            ItemFlowDetails(
                item="surplus",
                sources=(
                    ItemSource(scene="forge", command="award"),
                    ItemSource(scene="forge", command="bonus"),
                ),
                requirements=(),
                consumptions=(ItemConsumption(scene="forge", command="consume"),),
            ),
            ItemFlowDetails(
                item="deficit",
                sources=(ItemSource(scene="forge", command="award"),),
                requirements=(),
                consumptions=(
                    ItemConsumption(scene="forge", command="consume"),
                    ItemConsumption(scene="forge", command="extra"),
                ),
            ),
            ItemFlowDetails(
                item="orphaned",
                sources=(ItemSource(scene="forge", command="award"),),
                requirements=(),
                consumptions=(),
            ),
        )
    )

    details = {detail.item: detail for detail in report.items}
    assert details["balanced"].net_consumable_balance == 0
    assert details["balanced"].has_surplus_awards is False
    assert details["balanced"].has_consumption_deficit is False

    assert details["surplus"].net_consumable_balance == 1
    assert details["surplus"].has_surplus_awards is True
    assert details["surplus"].has_consumption_deficit is False

    assert details["deficit"].net_consumable_balance == -1
    assert details["deficit"].has_surplus_awards is False
    assert details["deficit"].has_consumption_deficit is True

    assert report.items_with_surplus_awards == ("surplus",)
    assert report.items_with_consumption_deficit == ("deficit",)


def test_analyse_item_flow_from_definitions_matches_direct() -> None:
    scenes = load_scenes_from_mapping(_ITEM_FLOW_SCENE_DEFINITIONS)
    direct = analyse_item_flow(scenes)
    via_definitions = analyse_item_flow_from_definitions(_ITEM_FLOW_SCENE_DEFINITIONS)

    assert via_definitions == direct


def test_format_item_flow_report_highlights_key_sections() -> None:
    report = analyse_item_flow_from_definitions(_ITEM_FLOW_SCENE_DEFINITIONS)
    formatted = format_item_flow_report(report)

    assert "Adventure Item Flow" in formatted
    assert "Item: hammer" in formatted
    assert "Sources:" in formatted
    assert "Required by:" in formatted
    assert "Consumed by:" in formatted
    assert "Items awarded but never used" in formatted
    assert "- herb" in formatted
    assert "Items referenced without a source" in formatted
    assert "- gold-key" in formatted


def test_format_item_flow_report_includes_balance_summary() -> None:
    report = ItemFlowReport(
        items=(
            ItemFlowDetails(
                item="surplus",
                sources=(
                    ItemSource(scene="forge", command="award"),
                    ItemSource(scene="forge", command="bonus"),
                ),
                requirements=(),
                consumptions=(ItemConsumption(scene="forge", command="consume"),),
            ),
            ItemFlowDetails(
                item="deficit",
                sources=(ItemSource(scene="forge", command="award"),),
                requirements=(),
                consumptions=(
                    ItemConsumption(scene="forge", command="consume"),
                    ItemConsumption(scene="forge", command="extra"),
                ),
            ),
        )
    )

    formatted = format_item_flow_report(report)

    assert (
        "Items awarded more times than they are consumed (potential surplus):"
        in formatted
    )
    assert "- surplus" in formatted
    assert (
        "Items consumed more times than they are awarded (potential deficit):"
        in formatted
    )
    assert "- deficit" in formatted


def test_compare_adventure_variants_highlights_metric_deltas() -> None:
    baseline_metrics = compute_adventure_complexity_from_definitions(
        _AB_TEST_BASELINE_DEFINITIONS
    )
    experiment_metrics = compute_adventure_complexity_from_definitions(
        _AB_TEST_EXPERIMENT_DEFINITIONS
    )

    report = compare_adventure_variants(
        baseline_metrics,
        experiment_metrics,
        variant_a_name="Baseline",
        variant_b_name="Experiment",
    )

    assert isinstance(report, AdventureABTestReport)
    delta_by_metric = {delta.metric: delta for delta in report.metric_deltas}

    scene_delta = delta_by_metric["scene_count"]
    assert scene_delta.absolute_difference == pytest.approx(1.0)
    assert scene_delta.relative_difference == pytest.approx(0.5)

    choice_delta = delta_by_metric["choice_count"]
    assert choice_delta.absolute_difference == pytest.approx(4.0)

    reward_delta = delta_by_metric["unique_item_reward_count"]
    assert reward_delta.absolute_difference == pytest.approx(2.0)
    assert reward_delta.relative_difference == pytest.approx(2.0)

    consumption_delta = delta_by_metric["unique_item_consumption_count"]
    assert consumption_delta.relative_difference is None

    assert report.awarded_item_changes == AdventureABCollectionDifference(
        added=("lens", "sigil"),
        removed=(),
    )
    assert report.consumed_item_changes == AdventureABCollectionDifference(
        added=("lens",),
        removed=(),
    )
    assert report.history_record_changes.added == (
        "claimed-sigil",
        "found-lens",
        "studied-carvings",
        "vault-opened",
    )
    assert report.history_record_changes.removed == ()


def test_compare_adventure_variants_from_definitions_matches_direct() -> None:
    baseline_metrics = compute_adventure_complexity_from_definitions(
        _AB_TEST_BASELINE_DEFINITIONS
    )
    experiment_metrics = compute_adventure_complexity_from_definitions(
        _AB_TEST_EXPERIMENT_DEFINITIONS
    )

    direct_report = compare_adventure_variants(
        baseline_metrics,
        experiment_metrics,
        variant_a_name="Baseline",
        variant_b_name="Experiment",
    )
    via_definitions = compare_adventure_variants_from_definitions(
        _AB_TEST_BASELINE_DEFINITIONS,
        _AB_TEST_EXPERIMENT_DEFINITIONS,
        variant_a_name="Baseline",
        variant_b_name="Experiment",
    )

    assert via_definitions == direct_report


def test_format_ab_test_report_lists_changes() -> None:
    report = compare_adventure_variants_from_definitions(
        _AB_TEST_BASELINE_DEFINITIONS,
        _AB_TEST_EXPERIMENT_DEFINITIONS,
        variant_a_name="Baseline",
        variant_b_name="Experiment",
    )

    formatted = format_ab_test_report(report)

    assert "A/B Test Comparison: Baseline vs Experiment" in formatted
    assert "- scene_count: Baseline 2 -> Experiment 3 [Δ +1 (+50.0%)]" in formatted
    assert "Unique items awarded:" in formatted
    assert "- Added in Experiment:" in formatted
    assert "  - lens" in formatted
    assert "History records:" in formatted
    assert "studied-carvings" in formatted


def test_compute_scene_reachability_raises_for_unknown_start() -> None:
    scenes = load_scenes_from_mapping(_REACHABILITY_SCENE_DEFINITIONS)

    with pytest.raises(ValueError):
        compute_scene_reachability(scenes, start_scene="missing")
