"""Common types, enums, and utilities shared across API models."""

from __future__ import annotations

import json
from enum import Enum
from functools import partial
from typing import Any, Callable, Literal, Mapping

from pydantic import BaseModel, Field
from starlette.background import BackgroundTask
from starlette.responses import JSONResponse


# Type aliases for validation and diff statuses
ValidationStatus = Literal["valid", "warnings", "errors"]
DiffStatus = Literal["added", "removed", "modified"]


# Collaboration TTL constants
_DEFAULT_COLLABORATION_TTL_SECONDS = 120
_MIN_COLLABORATION_TTL_SECONDS = 30
_MAX_COLLABORATION_TTL_SECONDS = 3600


class _UnsetType:
    """Sentinel indicating that an optional field was not provided."""

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - trivial representation
        return "_UNSET"


_UNSET = _UnsetType()


class ExportFormat(str, Enum):
    """Available formatting styles for exported scene JSON."""

    MINIFIED = "minified"
    PRETTY = "pretty"


class CollaboratorRole(str, Enum):
    """Enumerated permission levels for project collaborators."""

    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


class ProjectPermissionError(RuntimeError):
    """Raised when a collaborator attempts an unauthorised project mutation."""

    def __init__(self, project_id: str, message: str) -> None:
        super().__init__(message)
        self.project_id = project_id


def _dumps_for_export_format(export_format: ExportFormat) -> Callable[[Any], str]:
    """Return a JSON dumps function configured for the given export format."""
    if export_format is ExportFormat.PRETTY:
        return partial(json.dumps, indent=2, ensure_ascii=False)

    return partial(json.dumps, separators=(",", ":"), ensure_ascii=False)


class FormattedJSONResponse(JSONResponse):
    """JSON response that respects minified vs pretty-print formatting styles."""

    def __init__(
        self,
        content: Any,
        *,
        export_format: ExportFormat,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
        media_type: str | None = "application/json",
        background: BackgroundTask | None = None,
    ) -> None:
        self._export_format = export_format
        super().__init__(
            content=content,
            status_code=status_code,
            headers=headers,
            media_type=media_type,
            background=background,
        )

    def render(self, content: Any) -> bytes:
        dumps = _dumps_for_export_format(self._export_format)
        return dumps(content).encode("utf-8")


class Pagination(BaseModel):
    """Pagination metadata returned alongside collection responses."""

    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    total_items: int = Field(..., ge=0)
    total_pages: int = Field(..., ge=0)


__all__ = [
    "ValidationStatus",
    "DiffStatus",
    "ExportFormat",
    "CollaboratorRole",
    "ProjectPermissionError",
    "FormattedJSONResponse",
    "Pagination",
    "_UNSET",
    "_UnsetType",
    "_DEFAULT_COLLABORATION_TTL_SECONDS",
    "_MIN_COLLABORATION_TTL_SECONDS",
    "_MAX_COLLABORATION_TTL_SECONDS",
]
