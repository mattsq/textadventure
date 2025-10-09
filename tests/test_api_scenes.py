"""Tests for the FastAPI scene collection endpoint."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

import pytest
from fastapi.testclient import TestClient

from textadventure.api import SceneApiSettings, create_app
from textadventure.api.backup import BackupUploadMetadata
from textadventure.api.app import (
    CURRENT_SCENE_SCHEMA_VERSION,
    ExportFormat,
    ImportStrategy,
    SceneBranchStore,
    SceneRepository,
    SceneService,
    _compute_validation_statuses,
)
from textadventure.scripted_story_engine import load_scenes_from_mapping


def _client() -> TestClient:
    return TestClient(create_app())


def _import_dataset() -> dict[str, Any]:
    return {
        "alpha": {
            "description": "Alpha",
            "choices": [
                {"command": "forward", "description": "Move ahead."},
                {"command": "rest", "description": "Pause to recover."},
            ],
            "transitions": {
                "forward": {"narration": "You continue onward.", "target": "beta"},
                "rest": {"narration": "You take a brief rest.", "target": None},
            },
        },
        "beta": {
            "description": "Beta",
            "choices": [
                {"command": "return", "description": "Head back."},
            ],
            "transitions": {
                "return": {"narration": "You retrace your steps.", "target": "alpha"},
            },
        },
    }


def _expected_metadata(
    scenes: Mapping[str, Any], timestamp: datetime
) -> dict[str, str]:
    canonical = json.dumps(
        scenes,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    checksum = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    version_prefix = timestamp.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    version_id = f"{version_prefix}-{checksum[:8]}"
    return {
        "version_id": version_id,
        "checksum": checksum,
        "suggested_filename": f"scene-backup-{version_id}.json",
    }


def _write_dataset(path: Path, payload: Mapping[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle)


def test_openapi_documents_tag_metadata() -> None:
    client = _client()

    response = client.get("/openapi.json")
    assert response.status_code == 200

    schema = response.json()
    assert schema["info"]["description"].startswith(
        "HTTP API powering the text adventure editor"
    )

    tags = {entry["name"]: entry for entry in schema.get("tags", [])}
    expected_tags = {
        "Scenes",
        "Scene Branches",
        "Search",
        "Projects",
        "Project Templates",
        "Marketplace",
    }

    assert expected_tags.issubset(tags.keys())
    assert "scripted adventure scenes" in tags["Scenes"]["description"]
    assert "experimental scene branches" in tags["Scene Branches"]["description"]


def test_list_scenes_returns_expected_summary_fields() -> None:
    client = _client()

    response = client.get("/api/scenes")
    assert response.status_code == 200

    payload = response.json()
    assert payload["pagination"]["page"] == 1
    assert payload["pagination"]["page_size"] == 50
    assert payload["pagination"]["total_items"] >= len(payload["data"])

    summaries = {entry["id"]: entry for entry in payload["data"]}
    assert "starting-area" in summaries

    starting_area = summaries["starting-area"]
    assert starting_area["choice_count"] == 8
    assert starting_area["transition_count"] == 4
    assert starting_area["has_terminal_transition"] is True
    assert starting_area["validation_status"] in {"valid", "warnings", "errors"}

    updated_at = datetime.fromisoformat(starting_area["updated_at"])
    assert updated_at.tzinfo is not None


def test_search_filters_results_case_insensitively() -> None:
    client = _client()

    response = client.get("/api/scenes", params={"search": "Gate"})
    assert response.status_code == 200

    data = response.json()["data"]
    assert data, "Expected at least one scene to match search filter"
    for entry in data:
        combined = f"{entry['id']} {entry['description']}".casefold()
        assert "gate" in combined


def test_updated_after_filters_future_dates() -> None:
    client = _client()
    future_timestamp = datetime.now(timezone.utc) + timedelta(days=1)

    response = client.get(
        "/api/scenes",
        params={"updated_after": future_timestamp.isoformat()},
    )
    assert response.status_code == 200
    assert response.json()["data"] == []


def test_pagination_limits_results() -> None:
    client = _client()

    response = client.get("/api/scenes", params={"page_size": 1})
    assert response.status_code == 200

    payload = response.json()
    assert len(payload["data"]) == 1
    assert payload["pagination"]["page_size"] == 1


def test_get_scene_returns_full_definition_without_validation_block() -> None:
    client = _client()

    response = client.get("/api/scenes/starting-area")
    assert response.status_code == 200

    payload = response.json()
    assert payload["data"]["id"] == "starting-area"
    assert payload["data"]["choices"]
    assert payload["data"]["transitions"]
    assert payload.get("validation") is None

    created_at = datetime.fromisoformat(payload["data"]["created_at"])
    updated_at = datetime.fromisoformat(payload["data"]["updated_at"])
    assert created_at.tzinfo is not None
    assert updated_at.tzinfo is not None


def test_get_scene_returns_404_for_unknown_identifier() -> None:
    client = _client()

    response = client.get("/api/scenes/unknown")
    assert response.status_code == 404


def test_get_scene_can_include_validation_issues() -> None:
    class _StubRepository:
        def load(self) -> tuple[Mapping[str, Any], datetime]:
            definitions: Mapping[str, Any] = {
                "alpha": {
                    "description": "Alpha",
                    "choices": [
                        {"command": "use", "description": "Use the tool"},
                    ],
                    "transitions": {
                        "use": {
                            "narration": "You use the tool.",
                            "requires": ["widget"],
                            "narration_overrides": [
                                {
                                    "narration": " ",
                                    "requires_history_any": ["alpha-used"],
                                }
                            ],
                        }
                    },
                }
            }
            timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
            return definitions, timestamp

    service = SceneService(repository=_StubRepository())
    client = TestClient(create_app(scene_service=service))

    response = client.get("/api/scenes/alpha", params={"include_validation": "true"})
    assert response.status_code == 200

    payload = response.json()
    issues = payload["validation"]["issues"]
    assert issues, "Expected validation issues to be reported"

    codes = {issue["code"] for issue in issues}
    assert "missing_failure_narration" in codes
    assert "missing_override_narration" in codes

    failure_issue = next(
        issue for issue in issues if issue["code"] == "missing_failure_narration"
    )
    assert failure_issue["severity"] == "warning"
    assert failure_issue["path"] == "transitions.use.failure_narration"

    override_issue = next(
        issue for issue in issues if issue["code"] == "missing_override_narration"
    )
    assert override_issue["severity"] == "error"
    assert override_issue["path"] == "transitions.use.narration_overrides[0].narration"


def test_get_scene_graph_returns_nodes_and_edges() -> None:
    client = _client()

    response = client.get("/api/scenes/graph")
    assert response.status_code == 200

    payload = response.json()

    generated_at = datetime.fromisoformat(payload["generated_at"])
    assert generated_at.tzinfo is not None
    assert payload["start_scene"] == "starting-area"

    nodes = {entry["id"]: entry for entry in payload["nodes"]}
    assert "starting-area" in nodes
    assert nodes["starting-area"]["has_terminal_transition"] is True

    edges = {entry["id"]: entry for entry in payload["edges"]}

    assert "starting-area:explore" in edges
    explore_edge = edges["starting-area:explore"]
    assert explore_edge["target"] == "old-gate"
    assert explore_edge["is_terminal"] is False
    assert explore_edge["requires"] == []

    look_edge = edges["starting-area:look"]
    assert look_edge["target"] is None
    assert look_edge["is_terminal"] is True

    inspect_edge = edges["old-gate:inspect"]
    assert inspect_edge["item"] == "rusty key"

    hall_edge = edges["misty-courtyard:hall"]
    assert hall_edge["requires"] == ["rusty key"]
    assert hall_edge["failure_narration"]

    signal_edge = edges["ranger-lookout:signal"]
    assert signal_edge["override_count"] == 1


def test_get_scene_graph_supports_custom_start_scene() -> None:
    client = _client()

    response = client.get("/api/scenes/graph", params={"start_scene": "old-gate"})
    assert response.status_code == 200
    assert response.json()["start_scene"] == "old-gate"

    invalid = client.get("/api/scenes/graph", params={"start_scene": "unknown"})
    assert invalid.status_code == 400


def test_search_endpoint_returns_matches() -> None:
    client = _client()

    response = client.get("/api/search", params={"query": "gate"})
    assert response.status_code == 200

    payload = response.json()
    assert payload["query"] == "gate"
    assert payload["total_results"] >= 1
    assert payload["total_matches"] >= 1

    results = payload["results"]
    assert results, "Expected search to return at least one scene"
    first_result = results[0]
    assert "scene_id" in first_result
    assert first_result["match_count"] >= 1
    assert first_result["matches"]
    first_match = first_result["matches"][0]
    assert first_match["spans"], "Expected match spans to be included"


def test_search_endpoint_respects_limit_parameter() -> None:
    client = _client()

    response = client.get("/api/search", params={"query": "the", "limit": 1})
    assert response.status_code == 200

    payload = response.json()
    assert len(payload["results"]) == 1


def test_search_endpoint_rejects_blank_queries() -> None:
    client = _client()

    response = client.get("/api/search", params={"query": "   "})
    assert response.status_code == 400


def test_search_endpoint_can_filter_by_field_type() -> None:
    class _StubRepository:
        def load(self) -> tuple[Mapping[str, Any], datetime]:
            definitions: Mapping[str, Any] = {
                "alpha": {
                    "description": "Alpha ruins overlook the valley.",
                    "choices": [
                        {"command": "inspect", "description": "Inspect the carvings."},
                    ],
                    "transitions": {
                        "inspect": {
                            "narration": "The Alpha glyphs shimmer faintly.",
                        }
                    },
                },
                "beta": {
                    "description": "A quiet grove surrounds an ancient obelisk.",
                    "choices": [
                        {
                            "command": "whisper",
                            "description": "Whisper about the Alpha trail.",
                        }
                    ],
                    "transitions": {
                        "whisper": {
                            "narration": "The grove echoes the word alpha in reply.",
                        }
                    },
                },
            }
            timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
            return definitions, timestamp

    service = SceneService(repository=_StubRepository())
    client = TestClient(create_app(scene_service=service))

    unfiltered = client.get("/api/search", params={"query": "alpha"})
    assert unfiltered.status_code == 200
    scene_ids = {result["scene_id"] for result in unfiltered.json()["results"]}
    assert scene_ids == {"alpha", "beta"}

    filtered = client.get(
        "/api/search",
        params=[("query", "alpha"), ("field_types", "choice_description")],
    )
    assert filtered.status_code == 200

    payload = filtered.json()
    filtered_ids = {result["scene_id"] for result in payload["results"]}
    assert filtered_ids == {"beta"}

    for result in payload["results"]:
        assert result["matches"], "Expected field matches in filtered results"
        for match in result["matches"]:
            assert match["field_type"] == "choice_description"


def test_search_endpoint_can_filter_by_validation_status() -> None:
    class _StubRepository:
        def load(self) -> tuple[Mapping[str, Any], datetime]:
            definitions: Mapping[str, Any] = {
                "valid-scene": {
                    "description": "Alpha winds through a serene pass.",
                    "choices": [
                        {
                            "command": "walk",
                            "description": "Continue toward the Alpha ridge.",
                        },
                    ],
                    "transitions": {
                        "walk": {
                            "narration": "You follow the alpha ridge further north.",
                            "item": "rope",
                        }
                    },
                },
                "warning-scene": {
                    "description": "Alpha stones line a treacherous bridge.",
                    "choices": [
                        {
                            "command": "cross",
                            "description": "Attempt the Alpha crossing.",
                        },
                    ],
                    "transitions": {
                        "cross": {
                            "narration": "Each step echoes alpha into the canyon.",
                            "requires": ["rope"],
                        }
                    },
                },
                "error-scene": {
                    "description": " ",
                    "choices": [
                        {
                            "command": "signal",
                            "description": "Signal with an alpha flare.",
                        }
                    ],
                    "transitions": {
                        "signal": {
                            "narration": "",
                        }
                    },
                },
            }
            timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
            return definitions, timestamp

    service = SceneService(repository=_StubRepository())
    client = TestClient(create_app(scene_service=service))

    response = client.get("/api/search", params={"query": "alpha"})
    assert response.status_code == 200
    all_ids = {result["scene_id"] for result in response.json()["results"]}
    assert all_ids == {"valid-scene", "warning-scene", "error-scene"}

    def _fetch_ids(*statuses: str) -> set[str]:
        params = {"query": "alpha"}
        if statuses:
            params["validation_statuses"] = ",".join(statuses)

        response = client.get("/api/search", params=params)
        assert response.status_code == 200
        return {result["scene_id"] for result in response.json()["results"]}

    assert _fetch_ids("valid") == {"valid-scene"}
    assert _fetch_ids("warnings") == {"warning-scene"}
    assert _fetch_ids("errors") == {"error-scene"}
    assert _fetch_ids("valid", "warnings") == {"valid-scene", "warning-scene"}


def test_validate_endpoint_returns_combined_reports() -> None:
    client = _client()

    response = client.get("/api/scenes/validate")
    assert response.status_code == 200

    payload = response.json()
    data = payload["data"]
    generated_at = datetime.fromisoformat(data["generated_at"])
    assert generated_at.tzinfo is not None

    quality = data["quality"]
    assert "issue_count" in quality
    assert isinstance(quality["scenes_missing_description"], list)

    reachability = data["reachability"]
    assert reachability["start_scene"] == "starting-area"
    assert reachability["total_scene_count"] >= reachability["reachable_count"]

    item_flow = data["item_flow"]
    assert isinstance(item_flow["items"], list)
    if item_flow["items"]:
        first = item_flow["items"][0]
        assert set(first) >= {
            "item",
            "sources",
            "requirements",
            "consumptions",
            "is_orphaned",
        }


def test_validate_endpoint_rejects_unknown_start_scene() -> None:
    client = _client()

    response = client.get(
        "/api/scenes/validate", params={"start_scene": "unknown-scene"}
    )
    assert response.status_code == 400


def test_export_endpoint_returns_full_dataset() -> None:
    definitions: Mapping[str, Any] = {
        "alpha": {
            "description": "Alpha description",
            "choices": [
                {"command": "look", "description": "Look around"},
            ],
            "transitions": {
                "look": {
                    "narration": "You see the alpha ruins.",
                    "records": ["looked"],
                }
            },
        }
    }
    timestamp = datetime(2024, 1, 2, 12, tzinfo=timezone.utc)

    class _StubRepository:
        def load(self) -> tuple[Mapping[str, Any], datetime]:
            return definitions, timestamp

    service = SceneService(repository=_StubRepository())
    client = TestClient(create_app(scene_service=service))

    response = client.get("/api/export/scenes")
    assert response.status_code == 200

    payload = response.json()
    exported_timestamp = datetime.fromisoformat(payload["generated_at"])
    assert exported_timestamp == timestamp
    assert payload["scenes"] == definitions
    assert payload["metadata"] == _expected_metadata(definitions, timestamp)


def test_export_endpoint_filters_by_scene_ids() -> None:
    definitions: Mapping[str, Any] = {
        "alpha": {"description": "Alpha"},
        "beta": {"description": "Beta"},
        "gamma": {"description": "Gamma"},
    }
    timestamp = datetime(2024, 4, 5, 10, tzinfo=timezone.utc)

    class _StubRepository:
        def load(self) -> tuple[Mapping[str, Any], datetime]:
            return definitions, timestamp

    service = SceneService(repository=_StubRepository())
    client = TestClient(create_app(scene_service=service))

    response = client.get("/api/export/scenes", params={"ids": "gamma,alpha"})
    assert response.status_code == 200

    payload = response.json()
    expected_scenes = {
        "gamma": {"description": "Gamma"},
        "alpha": {"description": "Alpha"},
    }
    assert payload["scenes"] == expected_scenes
    assert payload["metadata"] == _expected_metadata(expected_scenes, timestamp)


def test_export_endpoint_returns_404_for_unknown_scene_id() -> None:
    definitions: Mapping[str, Any] = {"alpha": {"description": "Alpha"}}
    timestamp = datetime(2024, 4, 5, 10, tzinfo=timezone.utc)

    class _StubRepository:
        def load(self) -> tuple[Mapping[str, Any], datetime]:
            return definitions, timestamp

    service = SceneService(repository=_StubRepository())
    client = TestClient(create_app(scene_service=service))

    response = client.get("/api/export/scenes", params={"ids": "alpha,unknown"})
    assert response.status_code == 404


def test_export_endpoint_rejects_empty_ids_filter() -> None:
    definitions: Mapping[str, Any] = {"alpha": {"description": "Alpha"}}
    timestamp = datetime(2024, 4, 5, 10, tzinfo=timezone.utc)

    class _StubRepository:
        def load(self) -> tuple[Mapping[str, Any], datetime]:
            return definitions, timestamp

    service = SceneService(repository=_StubRepository())
    client = TestClient(create_app(scene_service=service))

    response = client.get("/api/export/scenes", params={"ids": "  ,  "})
    assert response.status_code == 400


def test_export_endpoint_supports_pretty_formatting() -> None:
    definitions: Mapping[str, Any] = {
        "alpha": {"description": "Alpha"},
    }
    timestamp = datetime(2024, 4, 5, 10, tzinfo=timezone.utc)

    class _StubRepository:
        def load(self) -> tuple[Mapping[str, Any], datetime]:
            return definitions, timestamp

    service = SceneService(repository=_StubRepository())
    client = TestClient(create_app(scene_service=service))

    response = client.get("/api/export/scenes", params={"format": "pretty"})
    assert response.status_code == 200

    expected = {
        "generated_at": timestamp.isoformat(),
        "scenes": definitions,
        "metadata": _expected_metadata(definitions, timestamp),
    }
    assert response.text == json.dumps(expected, indent=2, ensure_ascii=False)


def test_export_endpoint_supports_minified_formatting() -> None:
    definitions: Mapping[str, Any] = {
        "alpha": {"description": "Alpha"},
    }
    timestamp = datetime(2024, 4, 5, 10, tzinfo=timezone.utc)

    class _StubRepository:
        def load(self) -> tuple[Mapping[str, Any], datetime]:
            return definitions, timestamp

    service = SceneService(repository=_StubRepository())
    client = TestClient(create_app(scene_service=service))

    response = client.get("/api/export/scenes", params={"format": "minified"})
    assert response.status_code == 200

    expected = {
        "generated_at": timestamp.isoformat(),
        "scenes": definitions,
        "metadata": _expected_metadata(definitions, timestamp),
    }
    assert response.text == json.dumps(
        expected, separators=(",", ":"), ensure_ascii=False
    )


def test_export_scenes_alias_matches_legacy_endpoint() -> None:
    client = _client()

    legacy = client.get("/api/export/scenes")
    alias = client.get("/api/scenes/export")

    assert alias.status_code == legacy.status_code
    assert alias.content == legacy.content
    assert alias.headers["content-type"] == legacy.headers["content-type"]


def test_import_endpoint_validates_uploaded_scenes() -> None:
    client = _client()
    dataset = _import_dataset()

    response = client.post(
        "/api/import/scenes",
        json={"scenes": dataset, "start_scene": "alpha"},
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["scene_count"] == len(dataset)
    assert payload["start_scene"] == "alpha"

    validation = payload["validation"]
    generated_at = datetime.fromisoformat(validation["generated_at"])
    assert generated_at.tzinfo is not None
    assert validation["reachability"]["start_scene"] == "alpha"
    assert validation["reachability"]["reachable_count"] >= 1


def test_compute_validation_statuses_includes_item_flow_analysis() -> None:
    scenes = load_scenes_from_mapping(
        {
            "alpha": {
                "description": "Alpha",
                "choices": [
                    {"command": "take", "description": "Take the tool."},
                ],
                "transitions": {
                    "take": {
                        "narration": "You pick up the tool.",
                        "target": None,
                        "item": "tool",
                    }
                },
            },
            "beta": {
                "description": "Beta",
                "choices": [
                    {"command": "use", "description": "Use the relic."},
                ],
                "transitions": {
                    "use": {
                        "narration": "The door remains sealed.",
                        "target": None,
                        "requires": ["relic"],
                    }
                },
            },
        }
    )

    statuses = _compute_validation_statuses(scenes)

    assert statuses["beta"] == "errors"
    assert statuses["alpha"] == "warnings"


def test_import_endpoint_defaults_start_scene_to_first_entry() -> None:
    client = _client()
    dataset = _import_dataset()

    response = client.post(
        "/api/import/scenes",
        json={"scenes": dataset},
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["start_scene"] == "alpha"
    assert payload["scene_count"] == len(dataset)


def test_import_endpoint_rejects_unknown_start_scene() -> None:
    client = _client()
    dataset = _import_dataset()

    response = client.post(
        "/api/import/scenes",
        json={"scenes": dataset, "start_scene": "unknown"},
    )
    assert response.status_code == 400


def test_import_endpoint_returns_400_for_invalid_payload() -> None:
    client = _client()
    invalid_dataset = {
        "alpha": {
            "description": "Alpha",
            "choices": "not-a-list",
            "transitions": {},
        }
    }

    response = client.post(
        "/api/import/scenes",
        json={"scenes": invalid_dataset},
    )
    assert response.status_code == 400


def test_import_endpoint_migrates_legacy_schema_version_one() -> None:
    client = _client()
    legacy_dataset = {
        "alpha": {
            "description": "Alpha",
            "choices": {
                "forward": {"description": "Advance"},
                "rest": "Take a break",
            },
            "transitions": [
                {"command": "forward", "narration": "Go", "target": "beta"},
                {"command": "rest", "narration": "Pause"},
            ],
        },
        "beta": {
            "description": "Beta",
            "choices": [
                {"command": "return", "description": "Return"},
            ],
            "transitions": [
                {"command": "return", "narration": "Back", "target": "alpha"},
            ],
        },
    }

    response = client.post(
        "/api/import/scenes",
        json={
            "scenes": legacy_dataset,
            "schema_version": 1,
            "start_scene": "alpha",
        },
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["scene_count"] == len(legacy_dataset)
    assert payload["start_scene"] == "alpha"


def test_import_endpoint_rejects_newer_schema_version() -> None:
    client = _client()
    dataset = _import_dataset()

    response = client.post(
        "/api/import/scenes",
        json={"scenes": dataset, "schema_version": CURRENT_SCENE_SCHEMA_VERSION + 1},
    )
    assert response.status_code == 400


def test_import_scenes_alias_matches_legacy_endpoint() -> None:
    client = _client()
    dataset = _import_dataset()

    payload = {"scenes": dataset, "start_scene": "alpha"}

    legacy = client.post("/api/import/scenes", json=payload)
    alias = client.post("/api/scenes/import", json=payload)

    assert alias.status_code == legacy.status_code
    legacy_payload = legacy.json()
    alias_payload = alias.json()

    def _normalise(payload: dict[str, Any]) -> dict[str, Any]:
        normalised = copy.deepcopy(payload)
        validation = normalised.get("validation")
        if isinstance(validation, dict):
            validation.pop("generated_at", None)
        return normalised

    assert _normalise(alias_payload) == _normalise(legacy_payload)


def test_import_endpoint_reports_merge_and_replace_plans() -> None:
    timestamp = datetime(2024, 4, 12, 15, tzinfo=timezone.utc)

    existing: Mapping[str, Any] = {
        "alpha": {
            "description": "Alpha existing",
            "choices": [
                {"command": "wait", "description": "Wait patiently."},
            ],
            "transitions": {
                "wait": {"narration": "You remain still.", "target": None},
            },
        },
        "beta": {
            "description": "Beta original",
            "choices": [
                {"command": "advance", "description": "Advance cautiously."},
            ],
            "transitions": {
                "advance": {
                    "narration": "You follow the familiar path.",
                    "target": "alpha",
                }
            },
        },
        "gamma": {
            "description": "Gamma existing",
            "choices": [
                {"command": "depart", "description": "Leave the cavern."},
            ],
            "transitions": {
                "depart": {
                    "narration": "You depart without looking back.",
                    "target": None,
                }
            },
        },
    }

    class _StubRepository:
        def load(self) -> tuple[Mapping[str, Any], datetime]:
            return existing, timestamp

    service = SceneService(repository=_StubRepository())
    client = TestClient(create_app(scene_service=service))

    incoming = {
        "alpha": existing["alpha"],
        "beta": {
            "description": "Beta updated",
            "choices": [
                {"command": "advance", "description": "Advance cautiously."},
            ],
            "transitions": {
                "advance": {
                    "narration": "You follow a new path forward.",
                    "target": "alpha",
                }
            },
        },
        "delta": {
            "description": "Delta new",
            "choices": [
                {"command": "observe", "description": "Look around carefully."},
            ],
            "transitions": {
                "observe": {
                    "narration": "You take in the surroundings.",
                    "target": None,
                }
            },
        },
    }

    response = client.post("/api/import/scenes", json={"scenes": incoming})
    assert response.status_code == 200

    payload = response.json()
    plans = {entry["strategy"]: entry for entry in payload["plans"]}

    assert set(plans) == {"merge", "replace"}

    merge_plan = plans["merge"]
    assert merge_plan["new_scene_ids"] == ["delta"]
    assert merge_plan["updated_scene_ids"] == ["beta"]
    assert merge_plan["unchanged_scene_ids"] == ["alpha"]
    assert merge_plan["removed_scene_ids"] == []

    replace_plan = plans["replace"]
    assert replace_plan["new_scene_ids"] == ["delta"]
    assert replace_plan["updated_scene_ids"] == ["beta"]
    assert replace_plan["unchanged_scene_ids"] == ["alpha"]
    assert replace_plan["removed_scene_ids"] == ["gamma"]


def test_diff_scenes_reports_added_removed_and_modified_entries() -> None:
    timestamp = datetime(2024, 7, 1, 8, 30, tzinfo=timezone.utc)
    existing: Mapping[str, Any] = {
        "alpha": {
            "description": "Alpha original",
            "choices": [
                {"command": "wait", "description": "Wait patiently."},
            ],
            "transitions": {
                "wait": {"narration": "You wait in silence.", "target": None}
            },
        },
        "beta": {
            "description": "Beta original",
            "choices": [
                {"command": "press", "description": "Press forward."},
            ],
            "transitions": {
                "press": {
                    "narration": "You advance cautiously.",
                    "target": "alpha",
                }
            },
        },
        "gamma": {
            "description": "Gamma to remove",
            "choices": [],
            "transitions": {},
        },
    }

    class _StubRepository:
        def load(self) -> tuple[Mapping[str, Any], datetime]:
            return existing, timestamp

    service = SceneService(repository=_StubRepository())
    client = TestClient(create_app(scene_service=service))

    incoming = {
        "alpha": json.loads(json.dumps(existing["alpha"])),
        "beta": {
            "description": "Beta updated",
            "choices": [
                {"command": "press", "description": "Press forward."},
            ],
            "transitions": {
                "press": {
                    "narration": "You advance boldly.",
                    "target": "alpha",
                }
            },
        },
        "delta": {
            "description": "Delta newly added",
            "choices": [
                {"command": "explore", "description": "Explore the surroundings."},
            ],
            "transitions": {
                "explore": {
                    "narration": "You set off on a fresh path.",
                    "target": None,
                }
            },
        },
    }

    response = client.post("/api/scenes/diff", json={"scenes": incoming})
    assert response.status_code == 200

    payload = response.json()
    summary = payload["summary"]
    assert summary["added_scene_ids"] == ["delta"]
    assert summary["removed_scene_ids"] == ["gamma"]
    assert summary["modified_scene_ids"] == ["beta"]
    assert summary["unchanged_scene_ids"] == ["alpha"]

    entries_by_scene = {entry["scene_id"]: entry for entry in payload["entries"]}
    assert set(entries_by_scene) == {"beta", "gamma", "delta"}

    beta_diff = entries_by_scene["beta"]
    assert beta_diff["status"] == "modified"
    assert "--- current/beta" in beta_diff["diff"]
    assert "+++ incoming/beta" in beta_diff["diff"]
    assert '-  "description": "Beta original"' in beta_diff["diff"]
    assert '+  "description": "Beta updated"' in beta_diff["diff"]
    assert beta_diff["diff_html"].startswith("<table")
    assert "diff_chg" in beta_diff["diff_html"] or "diff_add" in beta_diff["diff_html"]

    gamma_diff = entries_by_scene["gamma"]
    assert gamma_diff["status"] == "removed"
    assert gamma_diff["diff"].startswith("--- current/gamma")
    assert gamma_diff["diff_html"].startswith("<table")
    assert "diff_sub" in gamma_diff["diff_html"]

    delta_diff = entries_by_scene["delta"]
    assert delta_diff["status"] == "added"
    assert "+++ incoming/delta" in delta_diff["diff"]
    assert delta_diff["diff_html"].startswith("<table")
    assert "diff_add" in delta_diff["diff_html"]


def test_diff_scenes_returns_unchanged_summary_when_payload_matches() -> None:
    timestamp = datetime(2024, 7, 2, 15, 45, tzinfo=timezone.utc)
    existing: Mapping[str, Any] = {
        "alpha": {
            "description": "Alpha scene",
            "choices": [
                {"command": "look", "description": "Survey the area."},
            ],
            "transitions": {
                "look": {"narration": "You take in the view.", "target": None}
            },
        },
        "beta": {
            "description": "Beta scene",
            "choices": [],
            "transitions": {},
        },
    }

    class _StubRepository:
        def load(self) -> tuple[Mapping[str, Any], datetime]:
            return existing, timestamp

    service = SceneService(repository=_StubRepository())
    client = TestClient(create_app(scene_service=service))

    response = client.post(
        "/api/scenes/diff",
        json={"scenes": json.loads(json.dumps(existing))},
    )
    assert response.status_code == 200

    payload = response.json()
    summary = payload["summary"]
    assert summary["added_scene_ids"] == []
    assert summary["removed_scene_ids"] == []
    assert summary["modified_scene_ids"] == []
    assert summary["unchanged_scene_ids"] == sorted(existing)
    assert payload["entries"] == []


def test_scene_service_creates_pretty_backup(tmp_path) -> None:
    dataset: Mapping[str, Any] = {
        "alpha": {
            "description": "Alpha scene",
            "choices": [{"command": "wait", "description": "Wait patiently."}],
            "transitions": {
                "wait": {
                    "narration": "You bide your time.",
                    "target": None,
                }
            },
        }
    }
    timestamp = datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc)

    class _StubRepository:
        def load(self) -> tuple[Mapping[str, Any], datetime]:
            return dataset, timestamp

    service = SceneService(repository=_StubRepository())
    export = service.export_scenes()

    backup_dir = tmp_path / "backups"
    result = service.create_backup(destination_dir=backup_dir)

    assert result.path.exists()
    assert result.path.parent == backup_dir
    assert backup_dir.is_dir()
    assert result.version_id == export.metadata.version_id
    assert result.checksum == export.metadata.checksum
    assert result.generated_at == export.generated_at
    assert result.path.name == export.metadata.suggested_filename

    expected_content = json.dumps(export.scenes, indent=2, ensure_ascii=False)
    assert result.path.read_text(encoding="utf-8") == expected_content
    assert json.loads(result.path.read_text(encoding="utf-8")) == export.scenes


def test_scene_service_creates_minified_backup(tmp_path) -> None:
    dataset: Mapping[str, Any] = {
        "alpha": {
            "description": "Alpha scene",
            "choices": [{"command": "wait", "description": "Wait patiently."}],
            "transitions": {
                "wait": {
                    "narration": "You bide your time.",
                    "target": None,
                }
            },
        }
    }
    timestamp = datetime(2024, 6, 2, 9, 30, tzinfo=timezone.utc)

    class _StubRepository:
        def load(self) -> tuple[Mapping[str, Any], datetime]:
            return dataset, timestamp

    service = SceneService(repository=_StubRepository())
    export = service.export_scenes()

    backup_dir = tmp_path / "minified"
    result = service.create_backup(
        destination_dir=backup_dir, export_format=ExportFormat.MINIFIED
    )

    assert result.path.parent == backup_dir
    expected_content = json.dumps(
        export.scenes, separators=(",", ":"), ensure_ascii=False
    )
    assert result.path.read_text(encoding="utf-8") == expected_content
    assert json.loads(result.path.read_text(encoding="utf-8")) == export.scenes


def test_scene_service_uploads_automatic_backup_to_cloud() -> None:
    initial_dataset: Mapping[str, Any] = {
        "alpha": {
            "description": "Alpha original",
            "choices": [
                {"command": "wait", "description": "Wait for a moment."},
            ],
            "transitions": {
                "wait": {
                    "narration": "You pause briefly.",
                    "target": None,
                }
            },
        }
    }
    initial_timestamp = datetime(2024, 7, 1, 10, 30, tzinfo=timezone.utc)

    class _Repository:
        def __init__(self) -> None:
            self._dataset = json.loads(json.dumps(initial_dataset))
            self._timestamp = initial_timestamp

        def load(self) -> tuple[Mapping[str, Any], datetime]:
            return json.loads(json.dumps(self._dataset)), self._timestamp

        def save(self, payload: Mapping[str, Any]) -> datetime:
            self._dataset = json.loads(json.dumps(payload))
            self._timestamp = self._timestamp + timedelta(minutes=5)
            return self._timestamp

    recorded_uploads: list[tuple[bytes, BackupUploadMetadata]] = []

    class _Recorder:
        def upload(self, *, content: bytes, metadata: BackupUploadMetadata) -> None:
            recorded_uploads.append((content, metadata))

    service = SceneService(
        repository=_Repository(),
        automatic_backup_dir=None,
        automatic_backup_uploaders=[_Recorder()],
    )

    updated_scene = {
        "description": "Alpha updated",
        "choices": [
            {"command": "wait", "description": "Wait for a moment."},
        ],
        "transitions": {
            "wait": {
                "narration": "You wait a little longer.",
                "target": None,
            }
        },
    }

    service.update_scene(
        scene_id="alpha",
        scene=updated_scene,
        schema_version=CURRENT_SCENE_SCHEMA_VERSION,
    )

    assert len(recorded_uploads) == 1
    payload, metadata = recorded_uploads[0]

    expected = _expected_metadata(initial_dataset, initial_timestamp)
    assert metadata.filename == expected["suggested_filename"]
    assert metadata.version_id == expected["version_id"]
    assert metadata.checksum == expected["checksum"]
    assert metadata.generated_at == initial_timestamp

    assert json.loads(payload.decode("utf-8")) == initial_dataset


def test_update_scene_creates_automatic_backup(tmp_path: Path) -> None:
    initial_dataset: Mapping[str, Any] = {
        "alpha": {
            "description": "Alpha original",
            "choices": [
                {"command": "wait", "description": "Wait for a moment."},
            ],
            "transitions": {
                "wait": {
                    "narration": "You pause briefly.",
                    "target": None,
                }
            },
        }
    }
    initial_timestamp = datetime(2024, 7, 1, 10, 30, tzinfo=timezone.utc)
    updated_timestamp = datetime(2024, 7, 1, 11, 0, tzinfo=timezone.utc)

    class _InMemoryRepository:
        def __init__(self) -> None:
            self._dataset = json.loads(json.dumps(initial_dataset))
            self._timestamp = initial_timestamp

        def load(self) -> tuple[Mapping[str, Any], datetime]:
            return json.loads(json.dumps(self._dataset)), self._timestamp

        def save(self, payload: Mapping[str, Any]) -> datetime:
            self._dataset = json.loads(json.dumps(payload))
            self._timestamp = updated_timestamp
            return self._timestamp

    repository = _InMemoryRepository()
    backup_dir = tmp_path / "auto-backups"
    service = SceneService(
        repository=repository,
        automatic_backup_dir=backup_dir,
    )

    updated_scene: Mapping[str, Any] = {
        "description": "Alpha revised",
        "choices": [
            {"command": "wait", "description": "Hold steady."},
        ],
        "transitions": {
            "wait": {
                "narration": "You continue to wait.",
                "target": None,
            }
        },
    }

    service.update_scene(
        scene_id="alpha",
        scene=updated_scene,
        schema_version=CURRENT_SCENE_SCHEMA_VERSION,
    )

    backups = list(backup_dir.glob("scene-backup-*.json"))
    assert len(backups) == 1

    backup_path = backups[0]
    expected_metadata = _expected_metadata(initial_dataset, initial_timestamp)
    assert backup_path.name == expected_metadata["suggested_filename"]
    assert json.loads(backup_path.read_text(encoding="utf-8")) == initial_dataset


def test_automatic_backup_retention_prunes_old_backups(tmp_path: Path) -> None:
    initial_dataset: Mapping[str, Any] = {
        "alpha": {
            "description": "Alpha original",
            "choices": [
                {"command": "wait", "description": "Wait it out."},
            ],
            "transitions": {
                "wait": {
                    "narration": "You stay put.",
                    "target": None,
                }
            },
        }
    }
    initial_timestamp = datetime(2024, 7, 2, 9, 0, tzinfo=timezone.utc)

    class _RollingRepository:
        def __init__(self) -> None:
            self._dataset = json.loads(json.dumps(initial_dataset))
            self._timestamp = initial_timestamp

        def snapshot(self) -> tuple[Mapping[str, Any], datetime]:
            return json.loads(json.dumps(self._dataset)), self._timestamp

        def load(self) -> tuple[Mapping[str, Any], datetime]:
            return self.snapshot()

        def save(self, payload: Mapping[str, Any]) -> datetime:
            self._dataset = json.loads(json.dumps(payload))
            self._timestamp = self._timestamp + timedelta(minutes=5)
            return self._timestamp

    repository = _RollingRepository()
    backup_dir = tmp_path / "retained"
    service = SceneService(
        repository=repository,
        automatic_backup_dir=backup_dir,
        automatic_backup_retention=2,
    )

    expected_filenames: list[str] = []

    for index in range(3):
        snapshot_dataset, snapshot_timestamp = repository.snapshot()
        expected = _expected_metadata(snapshot_dataset, snapshot_timestamp)[
            "suggested_filename"
        ]
        expected_filenames.append(expected)

        updated_scene = {
            "description": f"Alpha iteration {index}",
            "choices": [
                {
                    "command": "wait",
                    "description": f"Wait iteration {index}.",
                },
            ],
            "transitions": {
                "wait": {
                    "narration": f"You wait through iteration {index}.",
                    "target": None,
                }
            },
        }

        service.update_scene(
            scene_id="alpha",
            scene=updated_scene,
            schema_version=CURRENT_SCENE_SCHEMA_VERSION,
        )

    backups = sorted(path.name for path in backup_dir.glob("scene-backup-*.json"))
    assert len(backups) == 2
    assert backups == sorted(expected_filenames[-2:])


def test_scene_service_plans_rollback_to_backup_dataset() -> None:
    current_dataset: Mapping[str, Any] = {
        "alpha": {
            "description": "Alpha current",
            "choices": [
                {"command": "wait", "description": "Wait it out."},
            ],
            "transitions": {
                "wait": {
                    "narration": "You wait for a moment.",
                    "target": None,
                }
            },
        },
        "beta": {
            "description": "Beta current",
            "choices": [
                {"command": "proceed", "description": "Head forward."},
            ],
            "transitions": {
                "proceed": {
                    "narration": "You continue deeper into the cave.",
                    "target": "gamma",
                }
            },
        },
    }
    backup_dataset: Mapping[str, Any] = {
        "alpha": {
            "description": "Alpha legacy",
            "choices": [
                {"command": "wait", "description": "Wait patiently."},
            ],
            "transitions": {
                "wait": {
                    "narration": "You recall a simpler path.",
                    "target": None,
                }
            },
        }
    }
    current_timestamp = datetime(2024, 7, 1, 10, 0, tzinfo=timezone.utc)
    backup_timestamp = datetime(2024, 6, 20, 9, 30, tzinfo=timezone.utc)

    class _StubRepository:
        def load(self) -> tuple[Mapping[str, Any], datetime]:
            return current_dataset, current_timestamp

    service = SceneService(repository=_StubRepository())

    response = service.plan_rollback(
        scenes=backup_dataset, generated_at=backup_timestamp
    )

    expected_current = _expected_metadata(current_dataset, current_timestamp)
    assert response.current.generated_at == current_timestamp
    assert response.current.version_id == expected_current["version_id"]
    assert response.current.checksum == expected_current["checksum"]

    expected_target = _expected_metadata(backup_dataset, backup_timestamp)
    assert response.target.generated_at == backup_timestamp
    assert response.target.version_id == expected_target["version_id"]
    assert response.target.checksum == expected_target["checksum"]

    assert response.summary.added_scene_ids == []
    assert response.summary.removed_scene_ids == ["beta"]
    assert response.summary.modified_scene_ids == ["alpha"]

    entries_by_scene = {entry.scene_id: entry for entry in response.entries}
    assert set(entries_by_scene) == {"alpha", "beta"}
    assert entries_by_scene["alpha"].status == "modified"
    assert entries_by_scene["beta"].status == "removed"

    plan = response.plan
    assert plan.strategy is ImportStrategy.REPLACE
    assert plan.new_scene_ids == []
    assert plan.updated_scene_ids == ["alpha"]
    assert plan.removed_scene_ids == ["beta"]


def test_scene_service_computes_branch_plan() -> None:
    current_dataset: Mapping[str, Any] = {
        "alpha": {
            "description": "Alpha current",
            "choices": [
                {"command": "wait", "description": "Wait it out."},
            ],
            "transitions": {
                "wait": {
                    "narration": "You wait for a moment.",
                    "target": None,
                }
            },
        },
        "beta": {
            "description": "Beta current",
            "choices": [
                {"command": "proceed", "description": "Head forward."},
            ],
            "transitions": {
                "proceed": {
                    "narration": "You continue deeper into the cave.",
                    "target": "gamma",
                }
            },
        },
    }
    branch_dataset: Mapping[str, Any] = {
        "alpha": {
            "description": "Alpha branched",
            "choices": [
                {"command": "wait", "description": "Wait it out."},
            ],
            "transitions": {
                "wait": {
                    "narration": "You wait, spotting a hidden door.",
                    "target": "hidden-door",
                }
            },
        },
        "beta": current_dataset["beta"],
        "hidden-door": {
            "description": "A narrow doorway leads into darkness.",
            "choices": [
                {"command": "enter", "description": "Step into the dark."},
            ],
            "transitions": {
                "enter": {
                    "narration": "You steel yourself and enter the unknown.",
                    "target": None,
                }
            },
        },
    }
    current_timestamp = datetime(2024, 7, 1, 12, 0, tzinfo=timezone.utc)
    branch_timestamp = datetime(2024, 7, 2, 9, 15, tzinfo=timezone.utc)

    class _StubRepository:
        def load(self) -> tuple[Mapping[str, Any], datetime]:
            return current_dataset, current_timestamp

    expected_current = _expected_metadata(current_dataset, current_timestamp)
    expected_branch = _expected_metadata(branch_dataset, branch_timestamp)

    service = SceneService(repository=_StubRepository())

    response = service.plan_branch(
        branch_name="  Hidden Door Path  ",
        scenes=branch_dataset,
        schema_version=CURRENT_SCENE_SCHEMA_VERSION,
        generated_at=branch_timestamp,
        expected_base_version=expected_current["version_id"],
    )

    assert response.branch_name == "Hidden Door Path"
    assert response.base.version_id == expected_current["version_id"]
    assert response.base.checksum == expected_current["checksum"]
    assert response.base.generated_at == current_timestamp

    assert response.expected_base_version_id == expected_current["version_id"]
    assert response.base_version_matches is True

    assert response.target.version_id == expected_branch["version_id"]
    assert response.target.checksum == expected_branch["checksum"]
    assert response.target.generated_at == branch_timestamp

    assert response.summary.added_scene_ids == ["hidden-door"]
    assert response.summary.modified_scene_ids == ["alpha"]
    assert response.summary.removed_scene_ids == []

    assert len(response.plans) == 2
    merge_plan = next(
        plan for plan in response.plans if plan.strategy is ImportStrategy.MERGE
    )
    assert merge_plan.new_scene_ids == ["hidden-door"]
    assert merge_plan.updated_scene_ids == ["alpha"]
    assert merge_plan.unchanged_scene_ids == ["beta"]


def test_plan_rollback_endpoint_returns_expected_payload() -> None:
    current_dataset: Mapping[str, Any] = {
        "alpha": {
            "description": "Alpha current",
            "choices": [
                {"command": "wait", "description": "Wait it out."},
            ],
            "transitions": {
                "wait": {
                    "narration": "You wait for a moment.",
                    "target": None,
                }
            },
        }
    }
    backup_dataset: Mapping[str, Any] = {
        "alpha": {
            "description": "Alpha current",
            "choices": [
                {"command": "wait", "description": "Wait it out."},
            ],
            "transitions": {
                "wait": {
                    "narration": "You wait for a moment.",
                    "target": None,
                }
            },
        }
    }
    current_timestamp = datetime(2024, 7, 5, 8, 0, tzinfo=timezone.utc)
    backup_timestamp = datetime(2024, 6, 30, 18, 45, tzinfo=timezone.utc)

    class _StubRepository:
        def load(self) -> tuple[Mapping[str, Any], datetime]:
            return current_dataset, current_timestamp

    service = SceneService(repository=_StubRepository())
    client = TestClient(create_app(scene_service=service))

    response = client.post(
        "/api/scenes/rollback",
        json={
            "scenes": backup_dataset,
            "generated_at": backup_timestamp.isoformat(),
        },
    )

    assert response.status_code == 200
    payload = response.json()

    expected_current = _expected_metadata(current_dataset, current_timestamp)
    assert payload["current"]["version_id"] == expected_current["version_id"]
    assert payload["current"]["checksum"] == expected_current["checksum"]
    assert payload["current"]["generated_at"] == current_timestamp.isoformat()

    expected_target = _expected_metadata(backup_dataset, backup_timestamp)
    assert payload["target"]["version_id"] == expected_target["version_id"]
    assert payload["target"]["checksum"] == expected_target["checksum"]
    assert payload["target"]["generated_at"] == backup_timestamp.isoformat()

    assert payload["plan"]["strategy"] == "replace"
    assert payload["summary"]["added_scene_ids"] == []
    assert payload["summary"]["modified_scene_ids"] == []
    assert payload["summary"]["removed_scene_ids"] == []


def test_plan_branch_endpoint_reports_version_mismatch() -> None:
    current_dataset: Mapping[str, Any] = {
        "alpha": {
            "description": "Alpha current",
            "choices": [
                {"command": "wait", "description": "Wait it out."},
            ],
            "transitions": {
                "wait": {
                    "narration": "You wait for a moment.",
                    "target": None,
                }
            },
        }
    }
    branch_dataset: Mapping[str, Any] = {
        "alpha": {
            "description": "Alpha expanded",
            "choices": [
                {"command": "wait", "description": "Wait it out."},
                {"command": "explore", "description": "Explore the area."},
            ],
            "transitions": {
                "wait": {
                    "narration": "You wait patiently.",
                    "target": None,
                },
                "explore": {
                    "narration": "You find a branching passage.",
                    "target": "branching-passage",
                },
            },
        },
        "branching-passage": {
            "description": "A new passage opens before you.",
            "choices": [
                {"command": "continue", "description": "Head deeper."},
            ],
            "transitions": {
                "continue": {
                    "narration": "You continue onward.",
                    "target": None,
                }
            },
        },
    }
    current_timestamp = datetime(2024, 7, 10, 14, 30, tzinfo=timezone.utc)

    class _StubRepository:
        def load(self) -> tuple[Mapping[str, Any], datetime]:
            return current_dataset, current_timestamp

    service = SceneService(repository=_StubRepository())
    client = TestClient(create_app(scene_service=service))

    response = client.post(
        "/api/scenes/branches/plan",
        json={
            "branch_name": "New Passage",
            "scenes": branch_dataset,
            "schema_version": CURRENT_SCENE_SCHEMA_VERSION,
            "generated_at": datetime(
                2024, 7, 11, 8, 45, tzinfo=timezone.utc
            ).isoformat(),
            "base_version_id": "outdated-version",
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["branch_name"] == "New Passage"
    assert payload["expected_base_version_id"] == "outdated-version"
    assert payload["base_version_matches"] is False
    assert payload["summary"]["added_scene_ids"] == ["branching-passage"]
    assert payload["summary"]["modified_scene_ids"] == ["alpha"]


def test_create_branch_endpoint_persists_definition(tmp_path: Path) -> None:
    current_dataset: Mapping[str, Any] = {
        "alpha": {
            "description": "Alpha current",
            "choices": [
                {"command": "wait", "description": "Wait it out."},
            ],
            "transitions": {
                "wait": {
                    "narration": "You wait for a moment.",
                    "target": None,
                }
            },
        }
    }
    branch_dataset: Mapping[str, Any] = {
        "alpha": {
            "description": "Alpha expanded",
            "choices": [
                {"command": "wait", "description": "Wait it out."},
                {"command": "explore", "description": "Explore the area."},
            ],
            "transitions": {
                "wait": {
                    "narration": "You wait patiently.",
                    "target": None,
                },
                "explore": {
                    "narration": "You find a branching passage.",
                    "target": "branching-passage",
                },
            },
        },
        "branching-passage": {
            "description": "A new passage opens before you.",
            "choices": [
                {"command": "continue", "description": "Head deeper."},
            ],
            "transitions": {
                "continue": {
                    "narration": "You continue onward.",
                    "target": None,
                }
            },
        },
    }
    current_timestamp = datetime(2024, 7, 10, 14, 30, tzinfo=timezone.utc)
    branch_timestamp = datetime(2024, 7, 11, 8, 45, tzinfo=timezone.utc)

    class _StubRepository:
        def load(self) -> tuple[Mapping[str, Any], datetime]:
            return current_dataset, current_timestamp

    store = SceneBranchStore(root=tmp_path)
    service = SceneService(repository=_StubRepository(), branch_store=store)
    client = TestClient(create_app(scene_service=service))

    response = client.post(
        "/api/scenes/branches",
        json={
            "branch_name": "New Passage",
            "scenes": branch_dataset,
            "schema_version": CURRENT_SCENE_SCHEMA_VERSION,
            "generated_at": branch_timestamp.isoformat(),
            "base_version_id": "outdated-version",
        },
    )

    assert response.status_code == 201
    payload = response.json()

    expected_current = _expected_metadata(current_dataset, current_timestamp)
    expected_branch = _expected_metadata(branch_dataset, branch_timestamp)

    assert payload["id"] == "new-passage"
    assert payload["name"] == "New Passage"
    assert payload["scene_count"] == len(branch_dataset)
    assert payload["base"]["version_id"] == expected_current["version_id"]
    assert payload["target"]["version_id"] == expected_branch["version_id"]
    assert payload["expected_base_version_id"] == "outdated-version"
    assert payload["base_version_matches"] is False
    assert payload["summary"]["added_scene_ids"] == ["branching-passage"]
    assert payload["summary"]["modified_scene_ids"] == ["alpha"]

    listed = client.get("/api/scenes/branches")
    assert listed.status_code == 200
    listing = listed.json()
    assert listing["data"][0]["id"] == "new-passage"

    records = store.list()
    assert len(records) == 1
    record = records[0]
    assert record.plan.summary.added_scene_ids == ["branching-passage"]
    assert (
        record.scenes["branching-passage"]["description"]
        == branch_dataset["branching-passage"]["description"]
    )


def test_create_branch_endpoint_rejects_duplicate_identifier(tmp_path: Path) -> None:
    dataset: Mapping[str, Any] = {
        "alpha": {
            "description": "Alpha current",
            "choices": [
                {"command": "wait", "description": "Wait it out."},
            ],
            "transitions": {
                "wait": {
                    "narration": "You wait for a moment.",
                    "target": None,
                }
            },
        }
    }
    timestamp = datetime(2024, 7, 10, 14, 30, tzinfo=timezone.utc)

    class _StubRepository:
        def load(self) -> tuple[Mapping[str, Any], datetime]:
            return dataset, timestamp

    store = SceneBranchStore(root=tmp_path)
    service = SceneService(repository=_StubRepository(), branch_store=store)
    client = TestClient(create_app(scene_service=service))

    payload = {
        "branch_name": "Duplicate",
        "scenes": dataset,
        "schema_version": CURRENT_SCENE_SCHEMA_VERSION,
    }

    first = client.post("/api/scenes/branches", json=payload)
    assert first.status_code == 201

    second = client.post("/api/scenes/branches", json=payload)
    assert second.status_code == 409


def test_list_branches_endpoint_returns_empty_collection(tmp_path: Path) -> None:
    store = SceneBranchStore(root=tmp_path)
    service = SceneService(branch_store=store)
    client = TestClient(create_app(scene_service=service))

    response = client.get("/api/scenes/branches")
    assert response.status_code == 200
    assert response.json() == {"data": []}


def test_get_branch_endpoint_returns_branch_definition(tmp_path: Path) -> None:
    current_dataset: Mapping[str, Any] = {
        "alpha": {
            "description": "Alpha current",
            "choices": [
                {"command": "wait", "description": "Wait it out."},
            ],
            "transitions": {
                "wait": {
                    "narration": "You wait for a moment.",
                    "target": None,
                }
            },
        }
    }
    branch_dataset: Mapping[str, Any] = {
        "alpha": {
            "description": "Alpha branch",
            "choices": [
                {"command": "wait", "description": "Wait it out."},
            ],
            "transitions": {
                "wait": {
                    "narration": "You wait for a moment.",
                    "target": None,
                }
            },
        },
        "branching-passage": {
            "description": "A hidden corridor opens.",
            "choices": [
                {"command": "step", "description": "Step through."},
            ],
            "transitions": {
                "step": {
                    "narration": "You slip into the passage.",
                    "target": None,
                }
            },
        },
    }
    current_timestamp = datetime(2024, 7, 12, 10, 0, tzinfo=timezone.utc)
    branch_timestamp = datetime(2024, 7, 12, 11, 30, tzinfo=timezone.utc)

    class _StubRepository:
        def load(self) -> tuple[Mapping[str, Any], datetime]:
            return current_dataset, current_timestamp

    store = SceneBranchStore(root=tmp_path)
    service = SceneService(repository=_StubRepository(), branch_store=store)
    client = TestClient(create_app(scene_service=service))

    response = client.post(
        "/api/scenes/branches",
        json={
            "branch_name": "Hidden Passage",
            "scenes": branch_dataset,
            "schema_version": CURRENT_SCENE_SCHEMA_VERSION,
            "generated_at": branch_timestamp.isoformat(),
        },
    )
    assert response.status_code == 201
    identifier = response.json()["id"]

    detail = client.get(f"/api/scenes/branches/{identifier}")
    assert detail.status_code == 200

    payload = detail.json()
    expected_current = _expected_metadata(current_dataset, current_timestamp)
    expected_branch = _expected_metadata(branch_dataset, branch_timestamp)

    assert payload["id"] == identifier
    assert payload["name"] == "Hidden Passage"
    assert payload["scene_count"] == len(branch_dataset)
    assert payload["base"]["version_id"] == expected_current["version_id"]
    assert payload["target"]["version_id"] == expected_branch["version_id"]
    assert payload["summary"]["added_scene_ids"] == ["branching-passage"]

    entries = {entry["scene_id"]: entry for entry in payload["entries"]}
    assert entries["alpha"]["status"] == "modified"
    assert entries["branching-passage"]["status"] == "added"

    plans = {plan["strategy"]: plan for plan in payload["plans"]}
    assert set(plans) == {"merge", "replace"}
    assert plans["merge"]["new_scene_ids"] == ["branching-passage"]

    assert payload["scenes"] == branch_dataset


def test_get_branch_endpoint_returns_404_for_missing_branch(tmp_path: Path) -> None:
    store = SceneBranchStore(root=tmp_path)
    service = SceneService(branch_store=store)
    client = TestClient(create_app(scene_service=service))

    response = client.get("/api/scenes/branches/unknown")
    assert response.status_code == 404


def test_delete_branch_endpoint_removes_definition(tmp_path: Path) -> None:
    dataset: Mapping[str, Any] = {
        "alpha": {
            "description": "Alpha current",
            "choices": [
                {"command": "wait", "description": "Wait it out."},
            ],
            "transitions": {
                "wait": {
                    "narration": "You wait for a moment.",
                    "target": None,
                }
            },
        }
    }
    timestamp = datetime(2024, 7, 10, 14, 30, tzinfo=timezone.utc)

    class _StubRepository:
        def load(self) -> tuple[Mapping[str, Any], datetime]:
            return dataset, timestamp

    store = SceneBranchStore(root=tmp_path)
    service = SceneService(repository=_StubRepository(), branch_store=store)
    client = TestClient(create_app(scene_service=service))

    response = client.post(
        "/api/scenes/branches",
        json={
            "branch_name": "Ephemeral",
            "scenes": dataset,
            "schema_version": CURRENT_SCENE_SCHEMA_VERSION,
        },
    )
    assert response.status_code == 201
    identifier = response.json()["id"]

    delete_response = client.delete(f"/api/scenes/branches/{identifier}")
    assert delete_response.status_code == 204
    assert store.list() == []


def test_delete_branch_endpoint_returns_404_for_missing_branch(tmp_path: Path) -> None:
    store = SceneBranchStore(root=tmp_path)
    service = SceneService(branch_store=store)
    client = TestClient(create_app(scene_service=service))

    response = client.delete("/api/scenes/branches/missing")
    assert response.status_code == 404


def test_plan_rollback_endpoint_rejects_empty_payload() -> None:
    client = _client()

    response = client.post("/api/scenes/rollback", json={"scenes": {}})

    assert response.status_code == 400


def test_scene_repository_loads_from_configured_path(tmp_path: Path) -> None:
    dataset = _import_dataset()
    data_path = tmp_path / "scenes.json"
    _write_dataset(data_path, dataset)

    repository = SceneRepository(path=data_path)
    definitions, timestamp = repository.load()

    assert definitions == dataset
    assert timestamp.tzinfo is not None


def test_scene_api_settings_from_env(monkeypatch: Any, tmp_path: Path) -> None:
    data_path = tmp_path / "dataset.json"
    branch_root = tmp_path / "branches"
    template_root = tmp_path / "templates"
    backup_root = tmp_path / "backups"

    monkeypatch.setenv("TEXTADVENTURE_SCENE_PACKAGE", "my.package")
    monkeypatch.setenv("TEXTADVENTURE_SCENE_RESOURCE", "dataset.json")
    monkeypatch.setenv("TEXTADVENTURE_SCENE_PATH", str(data_path))
    monkeypatch.setenv("TEXTADVENTURE_BRANCH_ROOT", str(branch_root))
    monkeypatch.setenv("TEXTADVENTURE_PROJECT_ROOT", str(tmp_path / "projects"))
    monkeypatch.setenv("TEXTADVENTURE_PROJECT_TEMPLATE_ROOT", str(template_root))
    monkeypatch.setenv("TEXTADVENTURE_AUTOMATIC_BACKUP_DIR", str(backup_root))
    monkeypatch.setenv("TEXTADVENTURE_AUTOMATIC_BACKUP_RETENTION", "5")

    settings = SceneApiSettings.from_env()

    assert settings.scene_package == "my.package"
    assert settings.scene_resource_name == "dataset.json"
    assert settings.scene_path == data_path
    assert settings.branch_root == branch_root
    assert settings.project_root == tmp_path / "projects"
    assert settings.project_template_root == template_root
    assert settings.automatic_backup_dir == backup_root
    assert settings.automatic_backup_retention == 5


def test_scene_api_settings_ignore_blank_values(monkeypatch: Any) -> None:
    monkeypatch.setenv("TEXTADVENTURE_SCENE_PACKAGE", "   ")
    monkeypatch.setenv("TEXTADVENTURE_SCENE_RESOURCE", "   ")
    monkeypatch.setenv("TEXTADVENTURE_SCENE_PATH", "   ")
    monkeypatch.setenv("TEXTADVENTURE_BRANCH_ROOT", "")
    monkeypatch.setenv("TEXTADVENTURE_PROJECT_ROOT", "   ")
    monkeypatch.setenv("TEXTADVENTURE_PROJECT_TEMPLATE_ROOT", "")
    monkeypatch.setenv("TEXTADVENTURE_AUTOMATIC_BACKUP_DIR", " ")
    monkeypatch.delenv("TEXTADVENTURE_AUTOMATIC_BACKUP_RETENTION", raising=False)

    settings = SceneApiSettings.from_env()

    assert settings.scene_package == "textadventure.data"
    assert settings.scene_resource_name == "scripted_scenes.json"
    assert settings.scene_path is None
    assert settings.branch_root is None
    assert settings.project_root is None
    assert settings.project_template_root is None
    assert settings.automatic_backup_dir is None
    assert settings.automatic_backup_retention is None


def test_scene_api_settings_reject_invalid_backup_retention(monkeypatch: Any) -> None:
    monkeypatch.setenv("TEXTADVENTURE_AUTOMATIC_BACKUP_RETENTION", "0")
    with pytest.raises(ValueError):
        SceneApiSettings.from_env()

    monkeypatch.setenv("TEXTADVENTURE_AUTOMATIC_BACKUP_RETENTION", "not-a-number")
    with pytest.raises(ValueError):
        SceneApiSettings.from_env()


def test_update_scene_persists_changes_and_returns_version(tmp_path: Path) -> None:
    dataset = _import_dataset()
    data_path = tmp_path / "scenes.json"
    _write_dataset(data_path, dataset)

    initial_timestamp = datetime(2024, 3, 1, 12, tzinfo=timezone.utc)
    os.utime(data_path, (initial_timestamp.timestamp(), initial_timestamp.timestamp()))

    repository = SceneRepository(path=data_path)
    service = SceneService(repository=repository)
    client = TestClient(create_app(scene_service=service))

    stored_definitions, stored_timestamp = repository.load()
    metadata = _expected_metadata(stored_definitions, stored_timestamp)

    updated_scene: dict[str, Any] = {
        "description": "Alpha Revised",
        "choices": [
            {"command": "forward", "description": "Advance carefully."},
            {"command": "rest", "description": "Take a breather."},
        ],
        "transitions": {
            "forward": {"narration": "You advance with caution.", "target": "beta"},
            "rest": {"narration": "You pause to recover.", "target": None},
        },
    }

    response = client.put(
        "/api/scenes/alpha",
        json={
            "scene": updated_scene,
            "schema_version": CURRENT_SCENE_SCHEMA_VERSION,
            "expected_version_id": metadata["version_id"],
        },
    )

    assert response.status_code == 200

    payload = response.json()
    assert payload["data"]["id"] == "alpha"
    assert payload["data"]["description"] == "Alpha Revised"
    assert payload["data"]["choices"][0]["description"] == "Advance carefully."
    assert payload["validation"] is None

    version = payload["version"]
    updated_definitions, updated_timestamp = repository.load()
    expected_metadata = _expected_metadata(updated_definitions, updated_timestamp)

    assert version["version_id"] == expected_metadata["version_id"]
    assert version["checksum"] == expected_metadata["checksum"]
    assert datetime.fromisoformat(version["generated_at"]) == updated_timestamp

    assert updated_definitions["alpha"]["description"] == "Alpha Revised"
    assert updated_definitions["beta"] == dataset["beta"]


def test_update_scene_rejects_version_conflicts(tmp_path: Path) -> None:
    dataset = _import_dataset()
    data_path = tmp_path / "scenes.json"
    _write_dataset(data_path, dataset)

    timestamp = datetime(2024, 4, 1, 9, tzinfo=timezone.utc)
    os.utime(data_path, (timestamp.timestamp(), timestamp.timestamp()))

    repository = SceneRepository(path=data_path)
    service = SceneService(repository=repository)
    client = TestClient(create_app(scene_service=service))

    stored_definitions, stored_timestamp = repository.load()
    metadata = _expected_metadata(stored_definitions, stored_timestamp)

    response = client.put(
        "/api/scenes/alpha",
        json={
            "scene": dataset["alpha"],
            "schema_version": CURRENT_SCENE_SCHEMA_VERSION,
            "expected_version_id": "outdated-version",
        },
    )

    assert response.status_code == 409

    detail = response.json()["detail"]
    assert detail["current_version_id"] == metadata["version_id"]
    assert "message" in detail

    persisted_definitions, _ = repository.load()
    assert persisted_definitions == stored_definitions


def test_create_scene_persists_new_definition(tmp_path: Path) -> None:
    dataset = _import_dataset()
    data_path = tmp_path / "scenes.json"
    _write_dataset(data_path, dataset)

    repository = SceneRepository(path=data_path)
    service = SceneService(repository=repository)
    client = TestClient(create_app(scene_service=service))

    stored_definitions, stored_timestamp = repository.load()
    metadata = _expected_metadata(stored_definitions, stored_timestamp)

    new_scene = {
        "description": "Gamma",
        "choices": [
            {"command": "wait", "description": "Wait patiently."},
        ],
        "transitions": {
            "wait": {"narration": "Time drifts by.", "target": None},
        },
    }

    response = client.post(
        "/api/scenes",
        json={
            "id": "gamma",
            "scene": new_scene,
            "schema_version": CURRENT_SCENE_SCHEMA_VERSION,
            "expected_version_id": metadata["version_id"],
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["data"]["id"] == "gamma"
    assert payload["data"]["description"] == "Gamma"
    assert payload["validation"] is None

    updated_definitions, updated_timestamp = repository.load()
    expected_metadata = _expected_metadata(updated_definitions, updated_timestamp)

    version = payload["version"]
    assert version["version_id"] == expected_metadata["version_id"]
    assert version["checksum"] == expected_metadata["checksum"]
    assert "gamma" in updated_definitions
    assert updated_definitions["gamma"]["description"] == "Gamma"


def test_create_scene_rejects_existing_identifier(tmp_path: Path) -> None:
    dataset = _import_dataset()
    data_path = tmp_path / "scenes.json"
    _write_dataset(data_path, dataset)

    repository = SceneRepository(path=data_path)
    service = SceneService(repository=repository)
    client = TestClient(create_app(scene_service=service))

    stored_definitions, stored_timestamp = repository.load()
    metadata = _expected_metadata(stored_definitions, stored_timestamp)

    response = client.post(
        "/api/scenes",
        json={
            "id": "alpha",
            "scene": dataset["alpha"],
            "schema_version": CURRENT_SCENE_SCHEMA_VERSION,
            "expected_version_id": metadata["version_id"],
        },
    )

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_create_scene_rejects_version_conflicts(tmp_path: Path) -> None:
    dataset = _import_dataset()
    data_path = tmp_path / "scenes.json"
    _write_dataset(data_path, dataset)

    repository = SceneRepository(path=data_path)
    service = SceneService(repository=repository)
    client = TestClient(create_app(scene_service=service))

    stored_definitions, stored_timestamp = repository.load()
    metadata = _expected_metadata(stored_definitions, stored_timestamp)

    new_scene = {
        "description": "Gamma",
        "choices": [
            {"command": "wait", "description": "Wait patiently."},
        ],
        "transitions": {
            "wait": {"narration": "Time drifts by.", "target": None},
        },
    }

    response = client.post(
        "/api/scenes",
        json={
            "id": "gamma",
            "scene": new_scene,
            "schema_version": CURRENT_SCENE_SCHEMA_VERSION,
            "expected_version_id": "outdated-version",
        },
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["current_version_id"] == metadata["version_id"]

    persisted_definitions, _ = repository.load()
    assert persisted_definitions == stored_definitions


def test_delete_scene_removes_definition(tmp_path: Path) -> None:
    dataset = _import_dataset()
    dataset["gamma"] = {
        "description": "Gamma",
        "choices": [
            {"command": "wait", "description": "Wait patiently."},
        ],
        "transitions": {
            "wait": {"narration": "Time drifts by.", "target": None},
        },
    }

    data_path = tmp_path / "scenes.json"
    _write_dataset(data_path, dataset)

    repository = SceneRepository(path=data_path)
    service = SceneService(repository=repository)
    client = TestClient(create_app(scene_service=service))

    stored_definitions, stored_timestamp = repository.load()
    metadata = _expected_metadata(stored_definitions, stored_timestamp)

    response = client.delete(
        "/api/scenes/gamma",
        params={"expected_version_id": metadata["version_id"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["scene_id"] == "gamma"

    updated_definitions, updated_timestamp = repository.load()
    expected_metadata = _expected_metadata(updated_definitions, updated_timestamp)

    version = payload["version"]
    assert version["version_id"] == expected_metadata["version_id"]
    assert version["checksum"] == expected_metadata["checksum"]
    assert "gamma" not in updated_definitions


def test_delete_scene_rejects_unknown_identifier(tmp_path: Path) -> None:
    dataset = _import_dataset()
    data_path = tmp_path / "scenes.json"
    _write_dataset(data_path, dataset)

    repository = SceneRepository(path=data_path)
    service = SceneService(repository=repository)
    client = TestClient(create_app(scene_service=service))

    response = client.delete("/api/scenes/unknown")

    assert response.status_code == 404


def test_delete_scene_blocks_referenced_targets(tmp_path: Path) -> None:
    dataset = _import_dataset()
    data_path = tmp_path / "scenes.json"
    _write_dataset(data_path, dataset)

    repository = SceneRepository(path=data_path)
    service = SceneService(repository=repository)
    client = TestClient(create_app(scene_service=service))

    response = client.delete("/api/scenes/beta")

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert any(ref["scene_id"] == "alpha" for ref in detail["references"])


def test_create_app_uses_environment_scene_path(
    monkeypatch: Any, tmp_path: Path
) -> None:
    dataset = _import_dataset()
    data_path = tmp_path / "custom.json"
    _write_dataset(data_path, dataset)

    monkeypatch.setenv("TEXTADVENTURE_SCENE_PATH", str(data_path))

    client = TestClient(create_app())

    response = client.get("/api/scenes/alpha")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["description"] == "Alpha"


def test_create_app_uses_environment_branch_root(
    monkeypatch: Any, tmp_path: Path
) -> None:
    dataset = _import_dataset()
    data_path = tmp_path / "custom.json"
    branch_root = tmp_path / "branches"
    _write_dataset(data_path, dataset)

    monkeypatch.setenv("TEXTADVENTURE_SCENE_PATH", str(data_path))
    monkeypatch.setenv("TEXTADVENTURE_BRANCH_ROOT", str(branch_root))

    client = TestClient(create_app())

    payload = {
        "branch_name": "New storyline",
        "scenes": dataset,
        "schema_version": CURRENT_SCENE_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_version_id": None,
    }

    response = client.post("/api/scenes/branches", json=payload)
    assert response.status_code == 201
    assert branch_root.exists()
    assert any(branch_root.glob("*.json"))
