"""Pydantic models for user profile functionality.

This module defines the request and response models for the user profile API,
including user resource representations, listing, creation, and updates.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_serializer, field_validator, model_validator


class UserProfileResource(BaseModel):
    """Representation of a user account exposed through the API."""

    id: str = Field(..., description="Stable identifier for the user profile.")
    display_name: str = Field(
        ..., description="Human readable label to present in user interfaces."
    )
    email: str | None = Field(
        None, description="Optional contact email address associated with the user."
    )
    bio: str | None = Field(
        None, description="Optional free-form biography or profile summary."
    )
    created_at: datetime = Field(
        ..., description="Timestamp indicating when the profile was created."
    )
    updated_at: datetime = Field(
        ..., description="Timestamp indicating when the profile was last updated."
    )

    @field_serializer("created_at")
    def _serialise_created_at(self, value: datetime) -> str:
        return value.isoformat()

    @field_serializer("updated_at")
    def _serialise_updated_at(self, value: datetime) -> str:
        return value.isoformat()


class UserProfileListResponse(BaseModel):
    """Response envelope listing registered user profiles."""

    data: list[UserProfileResource] = Field(
        default_factory=list,
        description="Collection of user profiles ordered by identifier.",
    )


class UserProfileCreateRequest(BaseModel):
    """Request payload for creating a new user profile."""

    id: str = Field(..., description="Identifier to persist for the new profile.")
    display_name: str = Field(
        ..., description="Human readable name to associate with the profile."
    )
    email: str | None = Field(
        None, description="Optional contact email address for the profile."
    )
    bio: str | None = Field(
        None, description="Optional free-form biography to associate with the user."
    )

    @field_validator("display_name")
    @classmethod
    def _normalise_display_name(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Display name must be a non-empty string.")
        return trimmed

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            return None
        if "@" not in trimmed:
            raise ValueError("Email address must contain an '@' symbol.")
        return trimmed

    @field_validator("bio")
    @classmethod
    def _normalise_bio(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class UserProfileUpdateRequest(BaseModel):
    """Request payload for updating an existing user profile."""

    display_name: str | None = Field(
        None,
        description="Optional replacement for the human readable profile name.",
    )
    email: str | None = Field(
        None, description="Optional replacement contact email for the profile."
    )
    bio: str | None = Field(
        None, description="Optional replacement biography to persist for the user."
    )

    @field_validator("display_name")
    @classmethod
    def _normalise_display_name(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("Display name cannot be null when provided.")
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Display name must be a non-empty string when provided.")
        return trimmed

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            return None
        if "@" not in trimmed:
            raise ValueError("Email address must contain an '@' symbol.")
        return trimmed

    @field_validator("bio")
    @classmethod
    def _normalise_bio(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None

    @model_validator(mode="after")
    def _ensure_fields_provided(self) -> "UserProfileUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided to update a profile.")
        return self


__all__ = [
    "UserProfileResource",
    "UserProfileListResponse",
    "UserProfileCreateRequest",
    "UserProfileUpdateRequest",
]
