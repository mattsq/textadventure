"""Simple HTTP-less TestClient compatible with the shimmed FastAPI app."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, is_dataclass
from datetime import datetime
from queue import Empty
from typing import Any, Mapping, Literal
from urllib.parse import parse_qsl, urlparse

from .app import (
    FastAPI,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    _ClientCloseEvent,
    _ServerCloseMessage,
    _WebSocketState,
    _build_keyword_arguments,
)


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

    def websocket(self, path: str) -> "_WebSocketSession":
        parsed = urlparse(path)
        route_path = parsed.path or "/"
        route, path_params = self._app._resolve_websocket(route_path)
        query_params = dict(parse_qsl(parsed.query, keep_blank_values=True))
        state = _WebSocketState(
            route=route,
            path=route_path,
            path_params=path_params,
            query_params=query_params,
        )
        return _WebSocketSession(state)


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


class _WebSocketClient:
    """Client-facing handle for interacting with the WebSocket endpoint."""

    def __init__(self, state: _WebSocketState) -> None:
        self._state = state

    def send_json(self, message: Any) -> None:
        if self._state.closed:
            raise RuntimeError("WebSocket connection is closed.")
        self._state.incoming.put(message)

    def receive_json(self, timeout: float | None = None) -> Any:
        try:
            if timeout is None:
                message = self._state.outgoing.get()
            else:
                message = self._state.outgoing.get(timeout=timeout)
        except Empty as exc:  # pragma: no cover - exercised indirectly
            raise TimeoutError("Timed out waiting for WebSocket message.") from exc

        if isinstance(message, _ServerCloseMessage):
            self._state.closed = True
            self._state.close_code = message.code
            raise WebSocketDisconnect(message.code)

        return message

    def close(self, code: int = 1000) -> None:
        if self._state.closed:
            return
        self._state.closed = True
        self._state.close_code = code
        self._state.incoming.put(_ClientCloseEvent(code))


class _WebSocketSession:
    """Context manager that runs the WebSocket handler in a background thread."""

    def __init__(self, state: _WebSocketState) -> None:
        self._state = state
        self._client = _WebSocketClient(state)
        self._thread = threading.Thread(
            target=_run_websocket_endpoint, args=(state,), daemon=True
        )

    def __enter__(self) -> _WebSocketClient:
        self._thread.start()
        return self._client

    def __exit__(self, exc_type, exc, tb) -> Literal[False]:
        if not self._state.closed:
            self._client.close()
        self._thread.join()
        if self._state.exception is not None and exc_type is None:
            raise self._state.exception
        return False


def _run_websocket_endpoint(state: _WebSocketState) -> None:
    websocket = WebSocket(state)
    try:
        params: dict[str, Any] = dict(state.path_params)
        params["websocket"] = websocket
        kwargs = _build_keyword_arguments(state.route.endpoint, params)
        if "websocket" not in kwargs:
            kwargs["websocket"] = websocket
        state.route.endpoint(**kwargs)
    except WebSocketDisconnect:
        pass
    except BaseException as exc:  # pragma: no cover - bubble unexpected errors
        state.exception = exc
    finally:
        if not state.closed:
            state.closed = True
            state.outgoing.put(_ServerCloseMessage(state.close_code))
