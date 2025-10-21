"""FastAPI application exposing adventure scene management endpoints."""

from .app import create_app
from .settings import SceneApiSettings

# Re-export all models for backward compatibility
from .models import *  # noqa: F403

__all__ = [
    "create_app",
    "SceneApiSettings",
    # Models are exported via star import from .models
]
