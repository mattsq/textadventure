"""Very small subset of FastAPI used for local testing without dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from inspect import Parameter, Signature, signature
from types import NoneType, UnionType
from typing import Any, Callable, Mapping, MutableMapping
from typing import Union, get_args, get_origin, get_type_hints

from pydantic import BaseModel


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
    method: str
    path: str
    endpoint: Callable[..., Any]
    response_model: Any | None
    status_code: int | None = None


class FastAPI:
    """Extremely small FastAPI clone supporting declarative GET/POST routes."""

    def __init__(self, *, title: str = "", version: str = "") -> None:
        self.title = title
        self.version = version
        self._routes: MutableMapping[tuple[str, str], _Route] = {}

    def get(
        self,
        path: str,
        response_model: Any | None = None,
        *,
        status_code: int | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register a handler for ``GET`` requests."""

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self._routes[("GET", path)] = _Route(
                method="GET",
                path=path,
                endpoint=func,
                response_model=response_model,
                status_code=status_code,
            )
            return func

        return decorator

    def post(
        self,
        path: str,
        response_model: Any | None = None,
        *,
        status_code: int | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register a handler for ``POST`` requests."""

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self._routes[("POST", path)] = _Route(
                method="POST",
                path=path,
                endpoint=func,
                response_model=response_model,
                status_code=status_code,
            )
            return func

        return decorator

    def delete(
        self,
        path: str,
        response_model: Any | None = None,
        *,
        status_code: int | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register a handler for ``DELETE`` requests."""

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self._routes[("DELETE", path)] = _Route(
                method="DELETE",
                path=path,
                endpoint=func,
                response_model=response_model,
                status_code=status_code,
            )
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
