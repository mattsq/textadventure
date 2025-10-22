"""Minimal FastAPI-compatible shim for local development."""

from .app import (
    APIRouter,
    FastAPI,
    HTTPException,
    Query,
    Response,
    WebSocket,
    WebSocketDisconnect,
)

__all__ = [
    "APIRouter",
    "FastAPI",
    "HTTPException",
    "Query",
    "Response",
    "WebSocket",
    "WebSocketDisconnect",
]
