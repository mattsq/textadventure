import pytest

from textadventure.community_templates import (
    TemplateNotFoundError,
    get_community_template,
    list_community_templates,
    load_template_scenes,
)
from textadventure.scripted_story_engine import load_scenes_from_mapping


def test_templates_manifest_includes_known_entries() -> None:
    templates = list_community_templates()
    template_ids = {template.template_id for template in templates}

    assert "starter-forest" in template_ids
    assert "heist-blueprint" in template_ids

    for template in templates:
        assert template.summary
        assert template.scene_file.endswith(".json")
        assert template.tags


def test_templates_can_load_scene_definitions() -> None:
    template = get_community_template("starter-forest")
    scenes = template.load_scenes()

    assert "trailhead" in scenes

    # Ensure the scenes can be parsed by the scripted engine helpers without errors.
    load_scenes_from_mapping(scenes)


def test_load_template_scenes_matches_manifest() -> None:
    template = get_community_template("heist-blueprint")
    scenes = load_template_scenes(template.scene_file)

    assert "safehouse" in scenes


def test_unknown_template_raises() -> None:
    with pytest.raises(TemplateNotFoundError):
        get_community_template("missing-template")
