"""Configuration helpers for deploying the FastAPI scene service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


def _normalise_path(value: str | None) -> Path | None:
    if value is None:
        return None

    trimmed = value.strip()
    if not trimmed:
        return None

    return Path(trimmed).expanduser()


def _normalise_string(value: str | None, *, default: str) -> str:
    if value is None:
        return default

    trimmed = value.strip()
    return trimmed or default


@dataclass(frozen=True)
class SceneApiSettings:
    """Deployment settings for the FastAPI application.

    The helper reads from environment variables so the API can be configured without
    modifying application code. Paths are expanded to support ``~`` prefixes while
    empty strings are treated as if the variable was unset.
    """

    scene_package: str = "textadventure.data"
    scene_resource_name: str = "scripted_scenes.json"
    scene_path: Path | None = None
    branch_root: Path | None = None
    project_root: Path | None = None

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "SceneApiSettings":
        """Return settings populated from ``environ``.

        Args:
            environ: Optional mapping of environment variables. When omitted,
                :data:`os.environ` is used.
        """

        source = environ if environ is not None else os.environ

        scene_package = _normalise_string(
            source.get("TEXTADVENTURE_SCENE_PACKAGE"),
            default="textadventure.data",
        )
        scene_resource = _normalise_string(
            source.get("TEXTADVENTURE_SCENE_RESOURCE"),
            default="scripted_scenes.json",
        )
        scene_path = _normalise_path(source.get("TEXTADVENTURE_SCENE_PATH"))
        branch_root = _normalise_path(source.get("TEXTADVENTURE_BRANCH_ROOT"))
        project_root = _normalise_path(source.get("TEXTADVENTURE_PROJECT_ROOT"))

        return cls(
            scene_package=scene_package,
            scene_resource_name=scene_resource,
            scene_path=scene_path,
            branch_root=branch_root,
            project_root=project_root,
        )


__all__ = ["SceneApiSettings"]
