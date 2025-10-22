"""Pydantic models describing health and readiness responses."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HealthCheckResult(BaseModel):
    """Represents the outcome of an individual subsystem health check."""

    status: Literal["ok", "degraded", "error"] = Field(
        ..., description="Status indicator for the subsystem health check."
    )
    detail: str | None = Field(
        default=None,
        description="Optional human-readable context about the check result.",
    )


class HealthResponse(BaseModel):
    """Aggregated health information for the API service."""

    status: Literal["ok", "degraded", "error"] = Field(
        ..., description="Overall service health indicator."
    )
    checks: dict[str, HealthCheckResult] = Field(
        default_factory=dict,
        description="Mapping of subsystem identifiers to their health results.",
    )


class ReadinessResponse(BaseModel):
    """Readiness response indicating whether the service can handle requests."""

    status: Literal["ready"] = Field(
        ..., description="Readiness status for the service."
    )
    checks: dict[str, HealthCheckResult] = Field(
        default_factory=dict,
        description="Subsystem readiness details included in the response.",
    )


__all__ = [
    "HealthCheckResult",
    "HealthResponse",
    "ReadinessResponse",
]
