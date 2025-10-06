"""Minimal FastAPI-compatible shim for local development."""

from .app import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect

__all__ = ["FastAPI", "HTTPException", "Query", "WebSocket", "WebSocketDisconnect"]
