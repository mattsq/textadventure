"""Project-related Pydantic models and data structures.

This module contains all models related to adventure projects, including:
- Project resources and metadata
- Project templates
- Project assets and uploads
- Project collaborators and collaboration sessions
- Export and archive structures
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_serializer, field_validator

from .common import (
    CollaboratorRole,
    _MIN_COLLABORATION_TTL_SECONDS,
    _MAX_COLLABORATION_TTL_SECONDS,
)


class AdventureProjectResource(BaseModel):
    """Metadata describing an adventure project and its scene dataset."""

    id: str = Field(..., description="Stable identifier for the project.")
    name: str = Field(..., description="Display name for the project.")
    description: str | None = Field(
        None, description="Optional human readable project summary."
    )
    scene_count: int = Field(
        ..., ge=0, description="Number of scene definitions contained in the project."
    )
    collaborator_count: int = Field(
        ..., ge=0, description="Number of collaborators with access to the project."
    )
    created_at: datetime = Field(
        ..., description="Timestamp when the project metadata was last updated."
    )
    updated_at: datetime = Field(
        ..., description="Timestamp when the scene dataset was last updated."
    )
    version_id: str = Field(
        ...,
        description="Version identifier derived from the dataset timestamp and checksum.",
    )
    checksum: str = Field(
        ..., description="SHA-256 checksum of the serialised scene dataset."
    )

    @field_serializer("created_at")
    def _serialise_created_at(self, value: datetime) -> str:
        return value.isoformat()

    @field_serializer("updated_at")
    def _serialise_updated_at(self, value: datetime) -> str:
        return value.isoformat()


class AdventureProjectListResponse(BaseModel):
    """Response envelope describing available adventure projects."""

    data: list[AdventureProjectResource] = Field(
        default_factory=list,
        description="Collection of registered projects ordered by identifier.",
    )


class AdventureProjectTemplateResource(BaseModel):
    """Metadata describing an adventure project template."""

    id: str = Field(..., description="Stable identifier for the template.")
    name: str = Field(..., description="Display name for the template.")
    description: str | None = Field(
        None, description="Optional summary of the template adventure."
    )
    scene_count: int = Field(
        ..., ge=0, description="Number of scene definitions contained in the template."
    )
    created_at: datetime = Field(
        ..., description="Timestamp when the template metadata was last updated."
    )
    updated_at: datetime = Field(
        ..., description="Timestamp when the template dataset was last updated."
    )
    version_id: str = Field(
        ...,
        description="Version identifier derived from the template timestamp and checksum.",
    )
    checksum: str = Field(
        ..., description="SHA-256 checksum of the serialised template scene dataset."
    )

    @field_serializer("created_at")
    def _serialise_created_at(self, value: datetime) -> str:
        return value.isoformat()

    @field_serializer("updated_at")
    def _serialise_updated_at(self, value: datetime) -> str:
        return value.isoformat()


class AdventureProjectTemplateListResponse(BaseModel):
    """Response envelope describing available project templates."""

    data: list[AdventureProjectTemplateResource] = Field(
        default_factory=list,
        description="Collection of registered project templates ordered by identifier.",
    )


class ProjectTemplateInstantiateRequest(BaseModel):
    """Request payload for instantiating a project template."""

    project_id: str = Field(..., description="Identifier to assign to the new project.")
    name: str | None = Field(
        None,
        description="Optional display name to persist for the newly created project.",
    )
    description: str | None = Field(
        None, description="Optional summary describing the newly created project."
    )


class AdventureProjectDetailResponse(BaseModel):
    """Full project payload including the bundled scene dataset."""

    data: AdventureProjectResource = Field(
        ..., description="Metadata describing the requested project."
    )
    scenes: dict[str, Any] = Field(
        default_factory=dict,
        description="Scene definitions contained within the project dataset.",
    )


class ProjectAssetType(str, Enum):
    """Enumerated asset kinds surfaced by the project API."""

    FILE = "file"
    DIRECTORY = "directory"


class ProjectAssetResource(BaseModel):
    """Metadata describing an individual asset within a project."""

    path: str = Field(
        ..., description="Path relative to the project's assets directory."
    )
    name: str = Field(..., description="Basename of the asset entry.")
    type: ProjectAssetType = Field(
        ..., description="Indicates whether the entry is a file or directory."
    )
    size: int | None = Field(
        default=None,
        ge=0,
        description="File size in bytes when the asset is a file.",
    )
    content_type: str | None = Field(
        default=None,
        description="Best-effort MIME type derived from the filename.",
    )
    updated_at: datetime = Field(
        ..., description="Timestamp when the asset was last modified."
    )

    @field_serializer("updated_at")
    def _serialise_updated_at(self, value: datetime) -> str:
        return value.isoformat()


class ProjectAssetListResponse(BaseModel):
    """Response payload enumerating assets registered under a project."""

    project_id: str = Field(..., description="Identifier for the requested project.")
    root: str = Field(
        ..., description="Directory anchoring asset lookups for the project."
    )
    generated_at: datetime = Field(
        ..., description="Timestamp when the asset listing was generated."
    )
    assets: list[ProjectAssetResource] = Field(
        default_factory=list, description="Ordered collection of project assets."
    )

    @field_serializer("generated_at")
    def _serialise_generated_at(self, value: datetime) -> str:
        return value.isoformat()


@dataclass(frozen=True)
class ProjectAssetContent:
    """Binary payload representing an asset stored alongside a project."""

    filename: str
    content: bytes
    content_type: str | None


@dataclass(frozen=True)
class ProjectExportArchive:
    """ZIP archive containing a project's dataset, metadata, and assets."""

    project_id: str
    filename: str
    content: bytes
    content_type: str
    size: int
    generated_at: datetime
    version_id: str
    checksum: str


class ProjectAssetUploadRequest(BaseModel):
    """Payload describing the contents of an uploaded project asset."""

    content: str = Field(
        ..., description="Base64-encoded binary payload for the asset."
    )

    @field_validator("content")
    @classmethod
    def _validate_content(cls, value: str) -> str:
        try:
            base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError(
                "Asset content must be provided as base64-encoded data."
            ) from exc
        return value

    def decoded_content(self) -> bytes:
        return base64.b64decode(self.content)


class ProjectCollaboratorResource(BaseModel):
    """Representation of a collaborator's access level for a project."""

    user_id: str = Field(
        ..., description="Unique identifier for the collaborator (e.g. email)."
    )
    role: CollaboratorRole = Field(
        ..., description="Permission level granted to the collaborator."
    )
    display_name: str | None = Field(
        None,
        description="Optional human readable label for the collaborator.",
    )

    @field_validator("user_id")
    @classmethod
    def _validate_user_id(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Collaborator user_id must not be empty.")
        return trimmed

    @field_validator("display_name")
    @classmethod
    def _normalise_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class ProjectCollaboratorListResponse(BaseModel):
    """Response payload enumerating collaborators for a project."""

    project_id: str = Field(..., description="Identifier for the requested project.")
    collaborators: list[ProjectCollaboratorResource] = Field(
        default_factory=list,
        description="Ordered list of collaborators with access to the project.",
    )


class ProjectCollaboratorUpdateRequest(BaseModel):
    """Request body for replacing a project's collaborator roster."""

    collaborators: list[ProjectCollaboratorResource] = Field(
        default_factory=list,
        description="Complete collaborator list to persist for the project.",
    )


class ProjectCollaborationSessionResource(BaseModel):
    """Active collaboration session metadata exposed via the API."""

    session_id: str = Field(
        ..., description="Unique identifier representing the collaboration session."
    )
    user_id: str = Field(
        ..., description="Identifier of the collaborator associated with the session."
    )
    role: CollaboratorRole = Field(
        ..., description="Permission level granted to the collaborator."
    )
    display_name: str | None = Field(
        None, description="Optional display name resolved for the collaborator."
    )
    scene_id: str | None = Field(
        None,
        description="Optional scene identifier the collaborator is currently editing.",
    )
    started_at: datetime = Field(
        ..., description="Timestamp indicating when the session was created."
    )
    last_heartbeat: datetime = Field(
        ..., description="Timestamp for the most recent heartbeat received."
    )
    expires_at: datetime = Field(
        ..., description="Timestamp when the session will automatically expire."
    )

    @field_serializer("started_at")
    def _serialise_started_at(self, value: datetime) -> str:
        return value.isoformat()

    @field_serializer("last_heartbeat")
    def _serialise_last_heartbeat(self, value: datetime) -> str:
        return value.isoformat()

    @field_serializer("expires_at")
    def _serialise_expires_at(self, value: datetime) -> str:
        return value.isoformat()


class ProjectCollaborationSessionListResponse(BaseModel):
    """Response payload listing active collaboration sessions for a project."""

    project_id: str = Field(..., description="Identifier for the requested project.")
    sessions: list[ProjectCollaborationSessionResource] = Field(
        default_factory=list,
        description="Collection of active collaboration sessions.",
    )


class ProjectCollaborationSessionRequest(BaseModel):
    """Request body for joining or heartbeating a collaboration session."""

    session_id: str | None = Field(
        None,
        description="Existing session identifier to refresh. Omit to create a new session.",
    )
    scene_id: str | None = Field(
        None,
        description="Optional scene identifier describing the collaborator's focus.",
    )
    ttl_seconds: int | None = Field(
        None,
        ge=_MIN_COLLABORATION_TTL_SECONDS,
        le=_MAX_COLLABORATION_TTL_SECONDS,
        description=(
            "Requested inactivity timeout in seconds before the session expires."
        ),
    )


__all__ = [
    "AdventureProjectResource",
    "AdventureProjectListResponse",
    "AdventureProjectTemplateResource",
    "AdventureProjectTemplateListResponse",
    "ProjectTemplateInstantiateRequest",
    "AdventureProjectDetailResponse",
    "ProjectAssetType",
    "ProjectAssetResource",
    "ProjectAssetListResponse",
    "ProjectAssetContent",
    "ProjectExportArchive",
    "ProjectAssetUploadRequest",
    "ProjectCollaboratorResource",
    "ProjectCollaboratorListResponse",
    "ProjectCollaboratorUpdateRequest",
    "ProjectCollaborationSessionResource",
    "ProjectCollaborationSessionListResponse",
    "ProjectCollaborationSessionRequest",
]
