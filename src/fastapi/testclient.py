"""Simple HTTP-less TestClient compatible with the shimmed FastAPI app."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any, Mapping

from .app import FastAPI, HTTPException


class _Response:
    def __init__(
        self,
        status_code: int,
        payload: Any,
        text: str | None = None,
        *,
        headers: Mapping[str, Any] | None = None,
        content: bytes | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self._text = text
        self.headers = dict(headers or {})
        self._content = content

    def json(self) -> Any:
        return self._payload

    @property
    def text(self) -> str:
        if self._text is not None:
            return self._text
        return json.dumps(self._payload)

    @property
    def content(self) -> bytes:
        if self._content is not None:
            return self._content
        return self.text.encode("utf-8")


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

        payload, text, content, headers = _serialise(result)
        return _Response(status, payload, text, headers=headers, content=content)

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

        payload, text, content, headers = _serialise(result)
        return _Response(status, payload, text, headers=headers, content=content)

    def put(
        self,
        path: str,
        params: Mapping[str, Any] | None = None,
        json: Any | None = None,
    ) -> _Response:
        try:
            result, status = self._app._dispatch("PUT", path, params or {}, json)
        except HTTPException as exc:
            return _Response(exc.status_code, {"detail": exc.detail})

        payload, text, content, headers = _serialise(result)
        return _Response(status, payload, text, headers=headers, content=content)

    def delete(self, path: str, params: Mapping[str, Any] | None = None) -> _Response:
        try:
            result, status = self._app._dispatch("DELETE", path, params or {})
        except HTTPException as exc:
            return _Response(exc.status_code, {"detail": exc.detail})

        payload, text, content, headers = _serialise(result)
        return _Response(status, payload, text, headers=headers, content=content)


def _serialise(value: Any) -> tuple[Any, str | None, bytes | None, Mapping[str, Any]]:
    if hasattr(value, "body"):
        body = getattr(value, "body")
        headers_mapping = getattr(value, "headers", None)
        media_type = getattr(value, "media_type", None)

        content: bytes | None
        text: str | None

        if isinstance(body, (bytes, bytearray)):
            content = bytes(body)
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError:
                text = None
        else:
            text = str(body)
            content = text.encode("utf-8")

        headers: dict[str, Any] = dict(headers_mapping or {})
        if media_type and not any(key.lower() == "content-type" for key in headers):
            headers["content-type"] = media_type

        if text is None:
            payload: Any = content
        else:
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                payload = text

        return payload, text, content, headers

    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json"), None, None, {}
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value), None, None, {}
    if isinstance(value, list):
        return [_serialise(item)[0] for item in value], None, None, {}
    if isinstance(value, tuple):
        return [_serialise(item)[0] for item in value], None, None, {}
    if isinstance(value, dict):
        return {key: _serialise(item)[0] for key, item in value.items()}, None, None, {}
    if isinstance(value, datetime):
        return value.isoformat(), None, None, {}
    return value, None, None, {}
