from copy import deepcopy

from textadventure.scripted_story_engine import load_scenes_from_mapping
from textadventure.search import (
    search_scene_text,
    search_scene_text_from_definitions,
    replace_scene_text_in_definitions,
)


_SAMPLE_DEFINITIONS = {
    "trail": {
        "description": "A torch-lit trail winds toward a shadowed gate.",
        "choices": [
            {"command": "take", "description": "Take the torch from the sconce."},
            {"command": "wait", "description": "Wait for the guide."},
        ],
        "transitions": {
            "take": {
                "narration": "You secure the torch and feel braver already.",
            },
            "open": {
                "narration": "Torch held high, you tug at the gate.",
                "failure_narration": "Without the torch the darkness is overwhelming.",
                "narration_overrides": [
                    {
                        "narration": "Torch blazing, the gate opens without protest.",
                    }
                ],
            },
        },
    },
    "hall": {
        "description": "An empty hall stretches ahead.",
        "choices": [
            {"command": "listen", "description": "Listen for movement."},
        ],
        "transitions": {"listen": {"narration": "The hall remains quiet."}},
    },
}


def test_search_scene_text_finds_matches_across_fields() -> None:
    scenes = load_scenes_from_mapping(_SAMPLE_DEFINITIONS)

    results = search_scene_text(scenes, "torch")

    assert results.query == "torch"
    assert results.total_results == 1
    assert results.total_match_count == 6

    scene_result = results.results[0]
    assert scene_result.scene_id == "trail"
    assert scene_result.match_count == 6

    matches_by_path = {match.path: match for match in scene_result.matches}
    expected_paths = {
        "description",
        "choices.take.description",
        "transitions.take.narration",
        "transitions.open.narration",
        "transitions.open.failure_narration",
        "transitions.open.narration_overrides[0].narration",
    }
    assert matches_by_path.keys() == expected_paths

    description_match = matches_by_path["description"]
    assert description_match.field_type == "scene_description"
    assert description_match.match_count == 1
    first_span = description_match.spans[0]
    assert first_span.start == 2
    assert first_span.end == 7

    override_match = matches_by_path[
        "transitions.open.narration_overrides[0].narration"
    ]
    assert override_match.field_type == "override_narration"
    assert override_match.match_count == 1


def test_search_trims_query_whitespace() -> None:
    scenes = load_scenes_from_mapping(_SAMPLE_DEFINITIONS)

    results = search_scene_text(scenes, "  Torch  ")
    assert results.query == "Torch"
    assert results.total_results == 1


def test_search_rejects_empty_query() -> None:
    scenes = load_scenes_from_mapping(_SAMPLE_DEFINITIONS)

    try:
        search_scene_text(scenes, "   ")
    except ValueError as exc:
        assert "must not be empty" in str(exc)
    else:  # pragma: no cover - safeguard for failing test expectation
        raise AssertionError("Expected ValueError for empty search query")


def test_search_from_definitions_helper() -> None:
    results = search_scene_text_from_definitions(_SAMPLE_DEFINITIONS, "torch")
    assert results.total_results == 1


def test_search_scene_text_filters_allowed_field_types() -> None:
    scenes = load_scenes_from_mapping(_SAMPLE_DEFINITIONS)

    results = search_scene_text(
        scenes,
        "torch",
        field_types=["choice_description"],
    )

    assert results.total_results == 1
    scene_result = results.results[0]
    assert scene_result.scene_id == "trail"
    assert all(
        match.field_type == "choice_description" for match in scene_result.matches
    )


def test_search_scene_text_filters_scene_ids() -> None:
    scenes = load_scenes_from_mapping(_SAMPLE_DEFINITIONS)

    only_trail = search_scene_text(scenes, "torch", allowed_scene_ids=["trail"])
    assert {result.scene_id for result in only_trail.results} == {"trail"}

    only_hall = search_scene_text(scenes, "torch", allowed_scene_ids=["hall"])
    assert only_hall.total_results == 0


def test_replace_scene_text_updates_all_fields() -> None:
    definitions = deepcopy(_SAMPLE_DEFINITIONS)

    results = replace_scene_text_in_definitions(definitions, "torch", "lantern")

    trail = definitions["trail"]
    assert trail["description"] == "A lantern-lit trail winds toward a shadowed gate."
    assert trail["choices"][0]["description"] == "Take the lantern from the sconce."
    assert (
        trail["transitions"]["take"]["narration"]
        == "You secure the lantern and feel braver already."
    )
    assert (
        trail["transitions"]["open"]["failure_narration"]
        == "Without the lantern the darkness is overwhelming."
    )
    assert (
        trail["transitions"]["open"]["narration_overrides"][0]["narration"]
        == "lantern blazing, the gate opens without protest."
    )

    assert results.query == "torch"
    assert results.replacement_text == "lantern"
    assert results.total_results == 1
    assert results.total_replacement_count == 6

    scene_result = results.results[0]
    assert scene_result.scene_id == "trail"
    assert scene_result.replacement_count == 6
    replacements_by_path = {
        replacement.path: replacement for replacement in scene_result.replacements
    }
    assert replacements_by_path["description"].updated_text == trail["description"]
    assert (
        replacements_by_path["description"].original_text
        != replacements_by_path["description"].updated_text
    )


def test_replace_scene_text_respects_field_filters() -> None:
    definitions = deepcopy(_SAMPLE_DEFINITIONS)

    results = replace_scene_text_in_definitions(
        definitions,
        "torch",
        "lantern",
        field_types=["choice_description"],
    )

    trail = definitions["trail"]
    assert trail["description"].startswith("A torch")
    assert trail["choices"][0]["description"] == "Take the lantern from the sconce."
    assert trail["transitions"]["open"]["narration"].startswith("Torch held high")
    assert results.total_results == 1
    assert results.total_replacement_count == 1


def test_replace_scene_text_filters_allowed_scene_ids() -> None:
    definitions = deepcopy(_SAMPLE_DEFINITIONS)

    results = replace_scene_text_in_definitions(
        definitions,
        "hall",
        "corridor",
        allowed_scene_ids=["hall"],
    )

    assert definitions["hall"]["description"] == "An empty corridor stretches ahead."
    assert definitions["trail"]["description"].startswith("A torch")
    assert results.total_results == 1
    assert results.total_replacement_count == 2
    assert results.query == "hall"


def test_replace_scene_text_trims_query_whitespace() -> None:
    definitions = deepcopy(_SAMPLE_DEFINITIONS)

    results = replace_scene_text_in_definitions(definitions, "  hall  ", "corridor")

    assert results.query == "hall"
    assert results.total_replacement_count == 2


def test_replace_scene_text_rejects_empty_query() -> None:
    definitions = deepcopy(_SAMPLE_DEFINITIONS)

    try:
        replace_scene_text_in_definitions(definitions, "   ", "lantern")
    except ValueError as exc:
        assert "must not be empty" in str(exc)
    else:  # pragma: no cover - safeguard for failing test expectation
        raise AssertionError("Expected ValueError for empty replacement query")
