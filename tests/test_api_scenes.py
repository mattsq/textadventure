"""Tests for the FastAPI scene collection endpoint."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from fastapi.testclient import TestClient

from textadventure.api import create_app
from textadventure.api.app import (
    CURRENT_SCENE_SCHEMA_VERSION,
    ExportFormat,
    ImportStrategy,
    SceneBranchStore,
    SceneService,
)


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


def test_plan_rollback_endpoint_rejects_empty_payload() -> None:
    client = _client()

    response = client.post("/api/scenes/rollback", json={"scenes": {}})

    assert response.status_code == 400
