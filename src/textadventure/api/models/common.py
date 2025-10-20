"""Shared API models and type definitions used across modules."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

ValidationStatus = Literal["valid", "warnings", "errors"]

DiffStatus = Literal["added", "removed", "modified"]


class ExportFormat(str, Enum):
    """Available formatting styles for exported scene JSON."""

    MINIFIED = "minified"
    PRETTY = "pretty"


class Pagination(BaseModel):
    """Pagination metadata returned alongside collection responses."""

    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    total_items: int = Field(..., ge=0)
    total_pages: int = Field(..., ge=0)


__all__ = ["DiffStatus", "ExportFormat", "Pagination", "ValidationStatus"]
