"""Simple HTTP-less TestClient compatible with the shimmed FastAPI app."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any, Mapping

from .app import FastAPI, HTTPException


class _Response:
    def __init__(self, status_code: int, payload: Any) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        return self._payload


class TestClient:
    """Tiny stand-in for FastAPI's TestClient used in unit tests."""

    __test__ = False  # Prevent pytest from collecting this helper as a test case.

    def __init__(self, app: FastAPI) -> None:
        self._app = app

    def get(self, path: str, params: Mapping[str, Any] | None = None) -> _Response:
        try:
            result = self._app._dispatch("GET", path, params or {})
        except HTTPException as exc:
            return _Response(exc.status_code, {"detail": exc.detail})

        payload = _serialise(result)
        return _Response(200, payload)


def _serialise(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")  # type: ignore[call-arg]
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, list):
        return [_serialise(item) for item in value]
    if isinstance(value, tuple):
        return [_serialise(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialise(item) for key, item in value.items()}
    if isinstance(value, datetime):
        return value.isoformat()
    return value
