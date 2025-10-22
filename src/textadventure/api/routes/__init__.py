"""FastAPI route modules organized by domain."""

from __future__ import annotations

from .assets import create_assets_router
from .forum import create_forum_router
from .health import create_health_router
from .marketplace import create_marketplace_router
from .playtest import create_playtest_router
from .projects import create_projects_router
from .scenes import create_scenes_router
from .users import create_users_router

__all__ = [
    "create_assets_router",
    "create_forum_router",
    "create_health_router",
    "create_marketplace_router",
    "create_playtest_router",
    "create_projects_router",
    "create_scenes_router",
    "create_users_router",
]
