"""FastAPI application exposing read-only scene management endpoints."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
from typing import Any, Iterable, Mapping, Literal, cast

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from ..analytics import assess_adventure_quality
from ..scripted_story_engine import load_scenes_from_mapping

ValidationStatus = Literal["valid", "warnings", "errors"]


class Pagination(BaseModel):
    """Pagination metadata returned alongside collection responses."""

    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    total_items: int = Field(..., ge=0)
    total_pages: int = Field(..., ge=0)


class SceneSummary(BaseModel):
    """Lightweight representation of a scene for overview lists."""

    id: str
    description: str
    choice_count: int
    transition_count: int
    has_terminal_transition: bool
    validation_status: ValidationStatus
    updated_at: datetime


class SceneListResponse(BaseModel):
    """Response envelope for the scene collection endpoint."""

    data: list[SceneSummary]
    pagination: Pagination


@dataclass(frozen=True)
class SceneSummaryData:
    """Internal representation of a scene summary prior to serialisation."""

    id: str
    description: str
    choice_count: int
    transition_count: int
    has_terminal_transition: bool
    validation_status: ValidationStatus
    updated_at: datetime


class SceneRepository:
    """Loader responsible for retrieving the bundled scripted scene data."""

    def __init__(
        self,
        *,
        package: str = "textadventure.data",
        resource_name: str = "scripted_scenes.json",
    ) -> None:
        self._package = package
        self._resource_name = resource_name

    def load(self) -> tuple[Mapping[str, Any], datetime]:
        """Load scene definitions along with their last modified timestamp."""

        data_resource = resources.files(self._package).joinpath(self._resource_name)

        try:
            with resources.as_file(data_resource) as path:
                payload = _load_json(path)
                updated_at = _timestamp_for(path)
        except FileNotFoundError as exc:
            raise RuntimeError("Bundled scene data is missing.") from exc
        except OSError as exc:
            raise RuntimeError("Failed to read bundled scene data.") from exc

        if not isinstance(payload, Mapping):
            raise ValueError(
                "Scene data must be a mapping of identifiers to definitions."
            )

        return payload, updated_at


class SceneService:
    """Business logic supporting the API endpoints."""

    def __init__(self, repository: SceneRepository | None = None) -> None:
        self._repository = repository or SceneRepository()

    def list_scene_summaries(
        self,
        *,
        search: str | None,
        updated_after: datetime | None,
        include_validation: bool,
        page: int,
        page_size: int,
    ) -> SceneListResponse:
        definitions, dataset_timestamp = self._repository.load()
        scenes = load_scenes_from_mapping(definitions)

        validation_map = (
            _compute_validation_statuses(cast(Mapping[str, Any], scenes))
            if include_validation
            else {}
        )

        summaries = [
            SceneSummaryData(
                id=scene_id,
                description=scene.description,
                choice_count=len(scene.choices),
                transition_count=len(scene.transitions),
                has_terminal_transition=_has_terminal_transition(
                    scene.transitions.values()
                ),
                validation_status=validation_map.get(scene_id, "valid"),
                updated_at=dataset_timestamp,
            )
            for scene_id, scene in scenes.items()
        ]

        if search:
            lowered_query = search.casefold()
            summaries = [
                summary
                for summary in summaries
                if lowered_query in summary.id.casefold()
                or lowered_query in summary.description.casefold()
            ]

        if updated_after is not None:
            threshold = _ensure_timezone(updated_after)
            summaries = [
                summary for summary in summaries if summary.updated_at > threshold
            ]

        total_items = len(summaries)
        total_pages = _compute_total_pages(total_items, page_size)
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        visible = summaries[start_index:end_index]

        response = SceneListResponse(
            data=[SceneSummary(**asdict(summary)) for summary in visible],
            pagination=Pagination(
                page=page,
                page_size=page_size,
                total_items=total_items,
                total_pages=total_pages,
            ),
        )
        return response


def create_app(scene_service: SceneService | None = None) -> FastAPI:
    """Create a FastAPI app exposing the scene management endpoints."""

    service = scene_service or SceneService()
    app = FastAPI(title="Text Adventure Scene API", version="0.1.0")

    @app.get("/api/scenes", response_model=SceneListResponse)
    def get_scenes(
        *,
        search: str | None = Query(
            None, description="Filter by id or description substring."
        ),
        updated_after: datetime | None = Query(
            None, description="Return scenes updated after the provided ISO timestamp."
        ),
        include_validation: bool = Query(
            True,
            description="Include aggregated validation status metadata.",
        ),
        page: int = Query(1, ge=1),
        page_size: int = Query(
            50,
            ge=1,
            le=200,
            description="Number of results to return per page (max 200).",
        ),
    ) -> SceneListResponse:
        try:
            return service.list_scene_summaries(
                search=search,
                updated_after=updated_after,
                include_validation=include_validation,
                page=page,
                page_size=page_size,
            )
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return app


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _timestamp_for(path: Path) -> datetime:
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return datetime.now(timezone.utc)
    return datetime.fromtimestamp(mtime, tz=timezone.utc)


def _ensure_timezone(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _compute_total_pages(total_items: int, page_size: int) -> int:
    if total_items == 0:
        return 0
    return (total_items + page_size - 1) // page_size


def _has_terminal_transition(transitions: Iterable[Any]) -> bool:
    for transition in transitions:
        if getattr(transition, "target", None) is None:
            return True
    return False


def _compute_validation_statuses(
    scenes: Mapping[str, Any],
) -> dict[str, ValidationStatus]:
    report = assess_adventure_quality(cast(Mapping[str, Any], scenes))

    error_scenes: set[str] = set(report.scenes_missing_description)
    error_scenes.update(scene for scene, _ in report.transitions_missing_narration)
    error_scenes.update(
        scene for scene, _, _ in report.conditional_overrides_missing_narration
    )

    warning_scenes: set[str] = set(
        scene for scene, _ in report.choices_missing_description
    )
    warning_scenes.update(
        scene for scene, _ in report.gated_transitions_missing_failure
    )

    validation_map: dict[str, ValidationStatus] = {}
    for scene_id in scenes:
        if scene_id in error_scenes:
            validation_map[scene_id] = "errors"
        elif scene_id in warning_scenes:
            validation_map[scene_id] = "warnings"
        else:
            validation_map[scene_id] = "valid"

    return validation_map
