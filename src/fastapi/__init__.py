"""Minimal FastAPI-compatible shim for local development."""

from .app import FastAPI, HTTPException, Query

__all__ = ["FastAPI", "HTTPException", "Query"]
