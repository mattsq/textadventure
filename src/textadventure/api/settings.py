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
    project_template_root: Path | None = None
    user_root: Path | None = None
    automatic_backup_dir: Path | None = None
    automatic_backup_retention: int | None = None

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
        project_template_root = _normalise_path(
            source.get("TEXTADVENTURE_PROJECT_TEMPLATE_ROOT")
        )
        user_root = _normalise_path(source.get("TEXTADVENTURE_USER_ROOT"))
        automatic_backup_dir = _normalise_path(
            source.get("TEXTADVENTURE_AUTOMATIC_BACKUP_DIR")
        )

        automatic_backup_retention: int | None = None
        retention_raw = source.get("TEXTADVENTURE_AUTOMATIC_BACKUP_RETENTION")
        if retention_raw is not None:
            trimmed_retention = retention_raw.strip()
            if trimmed_retention:
                try:
                    parsed_retention = int(trimmed_retention)
                except ValueError as exc:
                    raise ValueError(
                        "TEXTADVENTURE_AUTOMATIC_BACKUP_RETENTION must be a positive integer."
                    ) from exc
                if parsed_retention < 1:
                    raise ValueError(
                        "TEXTADVENTURE_AUTOMATIC_BACKUP_RETENTION must be greater than zero."
                    )
                automatic_backup_retention = parsed_retention

        return cls(
            scene_package=scene_package,
            scene_resource_name=scene_resource,
            scene_path=scene_path,
            branch_root=branch_root,
            project_root=project_root,
            project_template_root=project_template_root,
            user_root=user_root,
            automatic_backup_dir=automatic_backup_dir,
            automatic_backup_retention=automatic_backup_retention,
        )


__all__ = ["SceneApiSettings"]
