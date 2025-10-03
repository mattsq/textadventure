"""Very small subset of FastAPI used for local testing without dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from inspect import Parameter, Signature, signature
from types import NoneType, UnionType
from typing import Any, Callable, Mapping, MutableMapping
from typing import Union, get_args, get_origin, get_type_hints


class HTTPException(Exception):
    """Exception mirroring FastAPI's HTTPException signature."""

    def __init__(self, status_code: int, detail: str | None = None) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def Query(default: Any = None, **_: Any) -> Any:
    """Return the provided default value, ignoring metadata arguments."""

    return default


@dataclass
class _Route:
    path: str
    endpoint: Callable[..., Any]
    response_model: Any | None


class FastAPI:
    """Extremely small FastAPI clone supporting declarative GET routes."""

    def __init__(self, *, title: str = "", version: str = "") -> None:
        self.title = title
        self.version = version
        self._routes: MutableMapping[str, _Route] = {}

    def get(
        self, path: str, response_model: Any | None = None
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register a handler for ``GET`` requests."""

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self._routes[path] = _Route(
                path=path, endpoint=func, response_model=response_model
            )
            return func

        return decorator

    def _resolve_route(self, path: str) -> tuple[_Route, dict[str, str]]:
        if path in self._routes:
            return self._routes[path], {}

        for route in self._routes.values():
            params = _match_path(route.path, path)
            if params is not None:
                return route, params

        raise HTTPException(404, f"Route '{path}' is not registered")

    def _dispatch(self, method: str, path: str, params: Mapping[str, Any]) -> Any:
        if method.upper() != "GET":
            raise HTTPException(405, f"Unsupported method '{method}'")

        route, path_params = self._resolve_route(path)
        combined_params: dict[str, Any] = dict(path_params)
        combined_params.update(params)
        kwargs = _build_keyword_arguments(route.endpoint, combined_params)
        return route.endpoint(**kwargs)


def _build_keyword_arguments(
    endpoint: Callable[..., Any], params: Mapping[str, Any]
) -> dict[str, Any]:
    bound_params: dict[str, Any] = {}
    sig: Signature = signature(endpoint)
    type_hints = get_type_hints(endpoint)

    for name, param in sig.parameters.items():
        if name in params:
            annotation = type_hints.get(name, param.annotation)
            bound_params[name] = _convert_value(params[name], annotation)
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

    if len(route_segments) != len(request_segments):
        return None

    params: dict[str, str] = {}
    for template_segment, actual_segment in zip(route_segments, request_segments):
        if template_segment.startswith("{") and template_segment.endswith("}"):
            param_name = template_segment[1:-1]
            if not param_name:
                return None
            params[param_name] = actual_segment
        elif template_segment != actual_segment:
            return None

    return params


def _convert_value(value: Any, annotation: Any) -> Any:
    if annotation is Parameter.empty or annotation is Any:
        return value

    origin = get_origin(annotation)
    if origin is None:
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
