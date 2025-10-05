"""Simple HTTP-less TestClient compatible with the shimmed FastAPI app."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any, Mapping

from .app import FastAPI, HTTPException


class _Response:
    def __init__(self, status_code: int, payload: Any, text: str | None = None) -> None:
        self.status_code = status_code
        self._payload = payload
        self._text = text

    def json(self) -> Any:
        return self._payload

    @property
    def text(self) -> str:
        if self._text is not None:
            return self._text
        return json.dumps(self._payload)


class TestClient:
    """Tiny stand-in for FastAPI's TestClient used in unit tests."""

    __test__ = False  # Prevent pytest from collecting this helper as a test case.

    def __init__(self, app: FastAPI) -> None:
        self._app = app

    def get(self, path: str, params: Mapping[str, Any] | None = None) -> _Response:
        try:
            result, status = self._app._dispatch("GET", path, params or {})
        except HTTPException as exc:
            return _Response(exc.status_code, {"detail": exc.detail})

        payload, text = _serialise(result)
        return _Response(status, payload, text)

    def post(
        self,
        path: str,
        params: Mapping[str, Any] | None = None,
        json: Any | None = None,
    ) -> _Response:
        try:
            result, status = self._app._dispatch("POST", path, params or {}, json)
        except HTTPException as exc:
            return _Response(exc.status_code, {"detail": exc.detail})

        payload, text = _serialise(result)
        return _Response(status, payload, text)

    def delete(self, path: str, params: Mapping[str, Any] | None = None) -> _Response:
        try:
            result, status = self._app._dispatch("DELETE", path, params or {})
        except HTTPException as exc:
            return _Response(exc.status_code, {"detail": exc.detail})

        payload, text = _serialise(result)
        return _Response(status, payload, text)


def _serialise(value: Any) -> tuple[Any, str | None]:
    if hasattr(value, "body"):
        body = getattr(value, "body")
        if isinstance(body, (bytes, bytearray)):
            text = body.decode("utf-8")
        else:
            text = str(body)

        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = text

        return payload, text

    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json"), None  # type: ignore[call-arg]
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value), None
    if isinstance(value, list):
        return [_serialise(item)[0] for item in value], None
    if isinstance(value, tuple):
        return [_serialise(item)[0] for item in value], None
    if isinstance(value, dict):
        return {key: _serialise(item)[0] for key, item in value.items()}, None
    if isinstance(value, datetime):
        return value.isoformat(), None
    return value, None
