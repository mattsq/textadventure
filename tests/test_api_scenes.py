"""Tests for the FastAPI scene collection endpoint."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from textadventure.api import create_app


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
