"""Health and readiness endpoints for the Text Adventure API."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from fastapi import APIRouter, HTTPException  # type: ignore[attr-defined]
from pydantic import ValidationError

from ..models import HealthCheckResult, HealthResponse, ReadinessResponse

HealthCheckCallable = Callable[[], HealthResponse | Mapping[str, Any]]
ReadinessCheckCallable = Callable[[], ReadinessResponse | Mapping[str, Any]]


def _coerce_health_response(
    payload: HealthResponse | Mapping[str, Any],
) -> HealthResponse:
    """Normalise arbitrary payloads into a ``HealthResponse`` instance."""

    if isinstance(payload, HealthResponse):
        return payload

    try:
        return HealthResponse.model_validate(payload)
    except ValidationError as exc:  # pragma: no cover - defensive branch
        raise HTTPException(
            status_code=500,
            detail="Health check callable returned invalid data.",
        ) from exc


def _coerce_readiness_response(
    payload: ReadinessResponse | Mapping[str, Any],
) -> ReadinessResponse:
    """Normalise arbitrary payloads into a ``ReadinessResponse`` instance."""

    if isinstance(payload, ReadinessResponse):
        return payload

    try:
        return ReadinessResponse.model_validate(payload)
    except ValidationError as exc:  # pragma: no cover - defensive branch
        raise HTTPException(
            status_code=500,
            detail="Readiness check callable returned invalid data.",
        ) from exc


def create_health_router(
    *,
    health_check: HealthCheckCallable | None = None,
    readiness_check: ReadinessCheckCallable | None = None,
) -> APIRouter:
    """Create an APIRouter exposing liveness and readiness endpoints."""

    router = APIRouter()

    @router.get(
        "/health",
        response_model=HealthResponse,
        tags=["Health"],
    )
    def get_health() -> HealthResponse:
        """Return the service health summary."""

        if health_check is None:
            return HealthResponse(status="ok")

        try:
            payload = health_check()
        except Exception as exc:  # pragma: no cover - defensive branch
            return HealthResponse(
                status="error",
                checks={
                    "health_check": HealthCheckResult(
                        status="error",
                        detail=str(exc),
                    )
                },
            )

        return _coerce_health_response(payload)

    @router.get(
        "/health/readiness",
        response_model=ReadinessResponse,
        tags=["Health"],
    )
    def get_readiness() -> ReadinessResponse:
        """Return the readiness status required for serving traffic."""

        if readiness_check is None:
            return ReadinessResponse(status="ready")

        try:
            payload = readiness_check()
        except Exception as exc:  # pragma: no cover - exercised in tests
            raise HTTPException(
                status_code=503,
                detail={"status": "unavailable", "reason": str(exc)},
            ) from exc

        return _coerce_readiness_response(payload)

    return router


__all__ = ["create_health_router"]
