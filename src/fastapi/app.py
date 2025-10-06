"""Very small subset of FastAPI used for local testing without dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from inspect import Parameter, Signature, signature
from types import NoneType, UnionType
from typing import Any, Callable, Mapping, MutableMapping, Sequence
from typing import Union, get_args, get_origin, get_type_hints
from queue import Queue

from pydantic import BaseModel


class HTTPException(Exception):
    """Exception mirroring FastAPI's HTTPException signature."""

    def __init__(self, status_code: int, detail: Any | None = None) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def Query(default: Any = None, **_: Any) -> Any:
    """Return the provided default value, ignoring metadata arguments."""

    return default


@dataclass
class _Route:
    method: str
    path: str
    endpoint: Callable[..., Any]
    response_model: Any | None
    status_code: int | None = None
    tags: tuple[str, ...] = ()


@dataclass
class _WebSocketRoute:
    path: str
    endpoint: Callable[..., Any]


@dataclass
class _ServerCloseMessage:
    code: int


@dataclass
class _ServerCloseSignal:
    code: int


@dataclass
class _ClientCloseEvent:
    code: int


class WebSocketDisconnect(Exception):
    """Raised when the WebSocket connection is terminated."""

    def __init__(self, code: int = 1000) -> None:
        super().__init__(f"WebSocket disconnected with code {code}")
        self.code = code


@dataclass
class _WebSocketState:
    route: _WebSocketRoute
    path: str
    path_params: Mapping[str, Any]
    query_params: Mapping[str, str]
    incoming: Queue[Any] = field(default_factory=Queue)
    outgoing: Queue[Any] = field(default_factory=Queue)
    accepted: bool = False
    closed: bool = False
    close_code: int = 1000
    exception: BaseException | None = None


class WebSocket:
    """Simplified WebSocket interface for the lightweight FastAPI shim."""

    def __init__(self, state: _WebSocketState) -> None:
        self._state = state

    @property
    def query_params(self) -> Mapping[str, str]:
        return self._state.query_params

    @property
    def path_params(self) -> Mapping[str, Any]:
        return self._state.path_params

    def accept(self) -> None:
        """Mark the connection as accepted."""

        self._state.accepted = True

    def receive_json(self) -> Any:
        """Return the next JSON message sent by the client."""

        if self._state.closed:
            raise WebSocketDisconnect(self._state.close_code)

        message = self._state.incoming.get()
        if isinstance(message, _ClientCloseEvent):
            self._state.closed = True
            self._state.close_code = message.code
            raise WebSocketDisconnect(message.code)
        if isinstance(message, _ServerCloseSignal):
            self._state.closed = True
            self._state.close_code = message.code
            raise WebSocketDisconnect(message.code)
        return message

    def send_json(self, message: Any) -> None:
        """Queue ``message`` so the client can receive it."""

        if self._state.closed:
            raise RuntimeError("WebSocket connection is closed.")
        self._state.outgoing.put(message)

    def close(self, code: int = 1000) -> None:
        """Close the connection with the provided ``code``."""

        if self._state.closed:
            return
        self._state.closed = True
        self._state.close_code = code
        self._state.outgoing.put(_ServerCloseMessage(code))
        self._state.incoming.put(_ServerCloseSignal(code))


class FastAPI:
    """Extremely small FastAPI clone supporting declarative GET/POST routes."""

    def __init__(
        self,
        *,
        title: str = "",
        version: str = "",
        description: str = "",
        openapi_tags: Sequence[Mapping[str, Any]] | None = None,
    ) -> None:
        self.title = title
        self.version = version
        self.description = description
        self.openapi_tags = (
            [dict(tag) for tag in openapi_tags] if openapi_tags is not None else []
        )
        self._routes: MutableMapping[tuple[str, str], _Route] = {}
        self._websocket_routes: list[_WebSocketRoute] = []

        def _openapi_handler() -> Mapping[str, Any]:
            return self.openapi()

        self.get("/openapi.json", status_code=200)(_openapi_handler)

    def get(
        self,
        path: str,
        response_model: Any | None = None,
        *,
        status_code: int | None = None,
        **kwargs: Any,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register a handler for ``GET`` requests."""

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            tags = tuple(str(tag) for tag in kwargs.get("tags", ()))
            self._routes[("GET", path)] = _Route(
                method="GET",
                path=path,
                endpoint=func,
                response_model=response_model,
                status_code=status_code,
                tags=tags,
            )
            return func

        return decorator

    def post(
        self,
        path: str,
        response_model: Any | None = None,
        *,
        status_code: int | None = None,
        **kwargs: Any,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register a handler for ``POST`` requests."""

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            tags = tuple(str(tag) for tag in kwargs.get("tags", ()))
            self._routes[("POST", path)] = _Route(
                method="POST",
                path=path,
                endpoint=func,
                response_model=response_model,
                status_code=status_code,
                tags=tags,
            )
            return func

        return decorator

    def put(
        self,
        path: str,
        response_model: Any | None = None,
        *,
        status_code: int | None = None,
        **kwargs: Any,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register a handler for ``PUT`` requests."""

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            tags = tuple(str(tag) for tag in kwargs.get("tags", ()))
            self._routes[("PUT", path)] = _Route(
                method="PUT",
                path=path,
                endpoint=func,
                response_model=response_model,
                status_code=status_code,
                tags=tags,
            )
            return func

        return decorator

    def delete(
        self,
        path: str,
        response_model: Any | None = None,
        *,
        status_code: int | None = None,
        **kwargs: Any,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register a handler for ``DELETE`` requests."""

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            tags = tuple(str(tag) for tag in kwargs.get("tags", ()))
            self._routes[("DELETE", path)] = _Route(
                method="DELETE",
                path=path,
                endpoint=func,
                response_model=response_model,
                status_code=status_code,
                tags=tags,
            )
            return func

        return decorator

    def openapi(self) -> Mapping[str, Any]:
        paths: dict[str, dict[str, Mapping[str, Any]]] = {}
        for route in self._routes.values():
            if route.path == "/openapi.json":
                continue
            method_spec: dict[str, Any] = {
                "responses": {"200": {"description": "Successful Response"}}
            }
            if route.tags:
                method_spec["tags"] = list(route.tags)
            paths.setdefault(route.path, {})[route.method.lower()] = method_spec

        return {
            "openapi": "3.0.0",
            "info": {
                "title": self.title,
                "version": self.version,
                "description": self.description,
            },
            "paths": paths,
            "tags": self.openapi_tags,
        }

    def websocket(
        self, path: str, **_: Any
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register a handler for WebSocket connections."""

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self._websocket_routes.append(_WebSocketRoute(path=path, endpoint=func))
            return func

        return decorator

    def _resolve_route(self, method: str, path: str) -> tuple[_Route, dict[str, str]]:
        key = (method, path)
        if key in self._routes:
            return self._routes[key], {}

        candidate_methods: set[str] = set()
        for (route_method, route_path), route in self._routes.items():
            params = _match_path(route_path, path)
            if params is None:
                continue
            if route_method == method:
                return route, params
            candidate_methods.add(route_method)

        if candidate_methods:
            allowed = ", ".join(sorted(candidate_methods))
            raise HTTPException(
                405,
                f"Method '{method}' not allowed for path '{path}'. Allowed: {allowed}.",
            )

        raise HTTPException(404, f"Route '{path}' is not registered")

    def _dispatch(
        self,
        method: str,
        path: str,
        params: Mapping[str, Any],
        body: Any | None = None,
    ) -> Any:
        route, path_params = self._resolve_route(method.upper(), path)
        combined_params: dict[str, Any] = dict(path_params)
        combined_params.update(params)
        kwargs = _build_keyword_arguments(route.endpoint, combined_params, body=body)
        result = route.endpoint(**kwargs)
        status = route.status_code or 200
        return result, status

    def _resolve_websocket(self, path: str) -> tuple[_WebSocketRoute, dict[str, str]]:
        for route in self._websocket_routes:
            params = _match_path(route.path, path)
            if params is not None:
                return route, params

        raise HTTPException(404, f"WebSocket route '{path}' is not registered")


def _build_keyword_arguments(
    endpoint: Callable[..., Any], params: Mapping[str, Any], *, body: Any | None = None
) -> dict[str, Any]:
    bound_params: dict[str, Any] = {}
    sig: Signature = signature(endpoint)
    type_hints = get_type_hints(endpoint)
    body_assigned = False

    for name, param in sig.parameters.items():
        if name in params:
            annotation = type_hints.get(name, param.annotation)
            bound_params[name] = _convert_value(params[name], annotation)
        elif not body_assigned and body is not None:
            annotation = type_hints.get(name, param.annotation)
            bound_params[name] = _convert_value(body, annotation)
            body_assigned = True
        elif param.default is Parameter.empty:
            # Parameter is required and has not been supplied. We deliberately
            # skip here so that Python's call will raise the appropriate TypeError.
            pass

    return bound_params


def _match_path(route_path: str, request_path: str) -> dict[str, str] | None:
    route_segments = [
        segment for segment in route_path.strip("/").split("/") if segment
    ]
    request_segments = [
        segment for segment in request_path.strip("/").split("/") if segment
    ]

    params: dict[str, str] = {}
    route_index = 0
    request_index = 0

    while route_index < len(route_segments):
        template_segment = route_segments[route_index]
        if template_segment.startswith("{") and template_segment.endswith("}"):
            inner = template_segment[1:-1]
            if not inner:
                return None

            if ":" in inner:
                name, converter = inner.split(":", 1)
            else:
                name, converter = inner, None

            if converter == "path":
                remaining = request_segments[request_index:]
                if route_index != len(route_segments) - 1:
                    return None
                params[name] = "/".join(remaining)
                return params

            if request_index >= len(request_segments):
                return None

            params[name] = request_segments[request_index]
            route_index += 1
            request_index += 1
            continue

        if request_index >= len(request_segments):
            return None

        if template_segment != request_segments[request_index]:
            return None

        route_index += 1
        request_index += 1

    if request_index != len(request_segments):
        return None

    return params


def _convert_value(value: Any, annotation: Any) -> Any:
    if annotation is Parameter.empty or annotation is Any:
        return value

    origin = get_origin(annotation)
    if origin is None:
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            if isinstance(value, annotation):
                return value
            if isinstance(value, Mapping):
                return annotation(**value)
        if annotation is dict and isinstance(value, Mapping):
            return dict(value)
        return _convert_primitive(value, annotation)

    args = get_args(annotation)

    if origin is list and isinstance(value, list):
        element_type = args[0] if args else Any
        return [_convert_value(item, element_type) for item in value]

    if origin is tuple and isinstance(value, tuple):
        return tuple(
            _convert_value(item, args[index] if index < len(args) else Any)
            for index, item in enumerate(value)
        )

    if origin is dict and isinstance(value, Mapping):
        key_type = args[0] if args else Any
        value_type = args[1] if len(args) > 1 else Any
        return {
            _convert_value(key, key_type): _convert_value(item, value_type)
            for key, item in value.items()
        }

    if origin in {Union, UnionType}:
        non_none_candidates = [
            candidate for candidate in args if candidate is not NoneType
        ]
        for candidate in non_none_candidates:
            try:
                return _convert_value(value, candidate)
            except (TypeError, ValueError, AttributeError):
                continue
        if NoneType in args and value in {None, "", "null"}:
            return None
        return value

    return value


def _convert_primitive(value: Any, annotation: Any) -> Any:
    if annotation is str:
        return str(value)
    if annotation is int:
        return int(value)
    if annotation is float:
        return float(value)
    if annotation is bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes"}:
                return True
            if lowered in {"false", "0", "no"}:
                return False
        return bool(value)
    if annotation is datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value)
    if annotation is type(None):
        return None

    return value
