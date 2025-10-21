"""Forum-related Pydantic models for the API.

This module contains all models related to forum threads and posts, including
request/response models for creating and listing forum content.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_serializer, field_validator

from .common import Pagination


# Regular expressions for forum identifier validation
_FORUM_IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_FORUM_SLUG_SANITISE_RE = re.compile(r"[^a-z0-9]+")


def _normalise_forum_identifier(identifier: str | None) -> str:
    """Normalise and validate a forum thread identifier.

    Args:
        identifier: The identifier string to normalise.

    Returns:
        The normalised identifier in lowercase with valid characters.

    Raises:
        ValueError: If the identifier is invalid or empty.
    """
    if not isinstance(identifier, str):
        raise ValueError("Forum thread identifier must be provided as a string.")

    slug = identifier.strip().casefold()
    if not slug:
        raise ValueError("Forum thread identifier must be a non-empty string.")

    if not _FORUM_IDENTIFIER_PATTERN.fullmatch(slug):
        raise ValueError(
            "Forum thread identifier must contain only lowercase letters, numbers, and hyphens."
        )

    return slug


class ForumPostResource(BaseModel):
    """Representation of a post within a forum thread exposed via the API."""

    id: str = Field(..., description="Stable identifier for the forum post.")
    author: str | None = Field(
        None,
        description="Optional display name associated with the post author.",
    )
    body: str = Field(..., description="Rendered message content for the post.")
    created_at: datetime = Field(
        ..., description="Timestamp describing when the post was created."
    )

    @field_serializer("created_at")
    def _serialise_created_at(self, value: datetime) -> str:
        return value.isoformat()


class ForumThreadSummary(BaseModel):
    """Lightweight overview of a forum discussion thread."""

    id: str = Field(..., description="Stable identifier for the forum thread.")
    title: str = Field(..., description="Title describing the discussion topic.")
    author: str | None = Field(
        None,
        description="Optional display name associated with the thread creator.",
    )
    created_at: datetime = Field(
        ..., description="Timestamp indicating when the thread was created."
    )
    updated_at: datetime = Field(
        ..., description="Timestamp of the most recent activity within the thread."
    )
    post_count: int = Field(
        ...,
        ge=0,
        description="Number of posts currently recorded for the thread.",
    )

    @field_serializer("created_at")
    def _serialise_created_at(self, value: datetime) -> str:
        return value.isoformat()

    @field_serializer("updated_at")
    def _serialise_updated_at(self, value: datetime) -> str:
        return value.isoformat()


class ForumThreadDetail(ForumThreadSummary):
    """Detailed representation of a forum thread including individual posts."""

    posts: list[ForumPostResource] = Field(
        default_factory=list,
        description="Collection of posts ordered chronologically within the thread.",
    )


class ForumThreadListResponse(BaseModel):
    """Response envelope describing paginated forum threads."""

    data: list[ForumThreadSummary] = Field(
        default_factory=list,
        description="Collection of forum threads ordered by recent activity.",
    )
    pagination: Pagination


class ForumThreadCreateRequest(BaseModel):
    """Request payload for creating a new forum discussion thread."""

    title: str = Field(..., description="Title describing the discussion topic.")
    body: str = Field(..., description="Initial post content for the new thread.")
    author: str | None = Field(
        None,
        description="Optional display name associated with the thread creator.",
    )
    identifier: str | None = Field(
        None,
        description="Optional custom identifier for the thread. Slugified when provided.",
    )

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise TypeError("Thread title must be provided as a string.")
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Thread title must be a non-empty string.")
        return trimmed

    @field_validator("body")
    @classmethod
    def _validate_body(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise TypeError("Thread body must be provided as a string.")
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Thread body must be a non-empty string.")
        return trimmed

    @field_validator("author", mode="before")
    @classmethod
    def _normalise_author(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            trimmed = value.strip()
            return trimmed or None
        raise TypeError("Author must be a string or null.")

    @field_validator("identifier")
    @classmethod
    def _validate_identifier(cls, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, str):
            raise TypeError("Thread identifier must be provided as a string.")
        return _normalise_forum_identifier(value)


class ForumPostCreateRequest(BaseModel):
    """Request payload for adding a reply to an existing forum thread."""

    body: str = Field(..., description="Content of the reply post.")
    author: str | None = Field(
        None,
        description="Optional display name associated with the post author.",
    )

    @field_validator("body")
    @classmethod
    def _validate_body(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise TypeError("Post body must be provided as a string.")
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Post body must be a non-empty string.")
        return trimmed

    @field_validator("author", mode="before")
    @classmethod
    def _normalise_author(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            trimmed = value.strip()
            return trimmed or None
        raise TypeError("Author must be a string or null.")


__all__ = [
    "ForumPostResource",
    "ForumThreadSummary",
    "ForumThreadDetail",
    "ForumThreadListResponse",
    "ForumThreadCreateRequest",
    "ForumPostCreateRequest",
]
