from fastapi import FastAPI
from fastapi.testclient import TestClient

from textadventure.api.models import (
    HealthCheckResult,
    HealthResponse,
    ReadinessResponse,
)
from textadventure.api.routes.health import create_health_router


def _create_client(**router_kwargs: object) -> TestClient:
    app = FastAPI()
    app.include_router(create_health_router(**router_kwargs))
    return TestClient(app)


def test_health_router_default_endpoints_return_ok() -> None:
    client = _create_client()

    health_response = client.get("/health")
    assert health_response.status_code == 200
    assert health_response.json() == {"status": "ok", "checks": {}}

    readiness_response = client.get("/health/readiness")
    assert readiness_response.status_code == 200
    assert readiness_response.json() == {"status": "ready", "checks": {}}


def test_health_router_coerces_models_and_mappings() -> None:
    def health_check() -> dict[str, object]:
        return {
            "status": "ok",
            "checks": {
                "storage": {
                    "status": "ok",
                    "detail": "connected",
                }
            },
        }

    def readiness_check() -> ReadinessResponse:
        return ReadinessResponse(
            status="ready",
            checks={
                "repository": HealthCheckResult(
                    status="ok",
                    detail="dataset available",
                )
            },
        )

    client = _create_client(
        health_check=health_check,
        readiness_check=readiness_check,
    )

    health_response = client.get("/health")
    assert health_response.status_code == 200
    assert health_response.json() == {
        "status": "ok",
        "checks": {
            "storage": {"status": "ok", "detail": "connected"},
        },
    }

    readiness_response = client.get("/health/readiness")
    assert readiness_response.status_code == 200
    assert readiness_response.json() == {
        "status": "ready",
        "checks": {
            "repository": {
                "status": "ok",
                "detail": "dataset available",
            }
        },
    }


def test_readiness_failure_returns_service_unavailable() -> None:
    def readiness_check() -> ReadinessResponse:
        raise RuntimeError("scene dataset missing")

    client = _create_client(readiness_check=readiness_check)

    response = client.get("/health/readiness")
    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "status": "unavailable",
            "reason": "scene dataset missing",
        }
    }


def test_health_check_exception_reports_error_status() -> None:
    def health_check() -> HealthResponse:
        raise RuntimeError("dependency offline")

    client = _create_client(health_check=health_check)

    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "error",
        "checks": {
            "health_check": {
                "status": "error",
                "detail": "dependency offline",
            }
        },
    }
