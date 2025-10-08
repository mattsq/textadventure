"""Helpers for discovering and loading bundled community templates."""

from __future__ import annotations

from dataclasses import dataclass
import json
from importlib import resources
from typing import Iterable, Mapping


class TemplateNotFoundError(KeyError):
    """Raised when a requested template identifier does not exist."""


@dataclass(frozen=True)
class CommunityTemplate:
    """Metadata describing a bundled community template."""

    template_id: str
    name: str
    summary: str
    tags: tuple[str, ...]
    scene_file: str
    recommended_use: str | None = None

    def load_scenes(self) -> Mapping[str, object]:
        """Load the scene definitions associated with this template."""

        return load_template_scenes(self.scene_file)


_MANIFEST_RESOURCE = "community_templates.json"
_TEMPLATES_CACHE: tuple[CommunityTemplate, ...] | None = None


def _load_manifest() -> Iterable[CommunityTemplate]:
    global _TEMPLATES_CACHE
    if _TEMPLATES_CACHE is not None:
        return _TEMPLATES_CACHE

    manifest_path = resources.files("textadventure.data").joinpath(_MANIFEST_RESOURCE)
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    templates: list[CommunityTemplate] = []

    for entry in manifest_data.get("templates", []):
        template = CommunityTemplate(
            template_id=entry["id"],
            name=entry["name"],
            summary=entry["summary"],
            tags=tuple(entry.get("tags", [])),
            scene_file=entry["scene_file"],
            recommended_use=entry.get("recommended_use"),
        )
        templates.append(template)

    _TEMPLATES_CACHE = tuple(templates)
    return _TEMPLATES_CACHE


def list_community_templates() -> list[CommunityTemplate]:
    """Return metadata for all bundled community templates."""

    return list(_load_manifest())


def get_community_template(template_id: str) -> CommunityTemplate:
    """Return the template metadata for the given identifier."""

    for template in _load_manifest():
        if template.template_id == template_id:
            return template
    raise TemplateNotFoundError(template_id)


def load_template_scenes(scene_file: str) -> Mapping[str, object]:
    """Load the raw scene definitions for a template JSON file."""

    resource_path = resources.files("textadventure.data").joinpath(scene_file)
    return json.loads(resource_path.read_text(encoding="utf-8"))
