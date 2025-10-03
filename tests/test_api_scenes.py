"""Tests for the FastAPI scene collection endpoint."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from fastapi.testclient import TestClient

from textadventure.api import create_app
from textadventure.api.app import SceneService


def _client() -> TestClient:
    return TestClient(create_app())


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
