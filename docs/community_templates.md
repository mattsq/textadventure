# Community Templates

The framework now bundles a small catalogue of community-authored starting points
that demonstrate different adventure patterns. Each template ships with rich
metadata so authors can quickly discover a scenario that matches the tone or
mechanics they want to explore before building custom content.

## Manifest structure

Bundled templates are defined in
[`textadventure/data/community_templates.json`](../src/textadventure/data/community_templates.json).
The manifest contains an array of templates with the following fields:

```json
{
  "templates": [
    {
      "id": "starter-forest",
      "name": "Starter Forest Expedition",
      "summary": "A compact three-scene adventure...",
      "tags": ["starter", "branching"],
      "scene_file": "templates/starter_forest.json",
      "recommended_use": "Use as a tutorial-friendly baseline..."
    }
  ]
}
```

- **`id`** — Stable identifier used when referencing the template.
- **`name`** — Human-friendly title shown in UIs or CLI listings.
- **`summary`** — High-level description of what the template covers.
- **`tags`** — Searchable keywords that highlight the mechanics showcased.
- **`scene_file`** — Relative path (within `textadventure.data`) to the scene
  JSON payload consumed by `ScriptedStoryEngine`.
- **`recommended_use`** — Optional author guidance with tips or best practices.

Individual scene payloads live under
[`textadventure/data/templates/`](../src/textadventure/data/templates/) and
follow the same schema used by `scripted_scenes.json`.

## Discovering templates in Python

Use the `textadventure.community_templates` helpers to explore and load bundled
templates:

```python
from textadventure import list_community_templates, get_community_template

templates = list_community_templates()
for template in templates:
    print(template.name, template.tags)

starter = get_community_template("starter-forest")
scene_definitions = starter.load_scenes()
```

`CommunityTemplate.load_scenes()` returns a mapping compatible with
`ScriptedStoryEngine`. Authors can feed these scenes directly into the engine or
use them as a baseline when crafting new adventures.

## Extending the catalogue

To contribute new templates:

1. Add a scene JSON file under `src/textadventure/data/templates/`.
2. Append an entry to `community_templates.json` pointing at the new file. Keep
   identifiers kebab-cased for consistency.
3. Update this documentation with a short blurb describing the new template's
   focus and recommended use cases.
4. Provide automated coverage verifying that the template loads correctly (see
   `tests/test_community_templates.py` for examples).

This workflow keeps the catalogue discoverable while ensuring every template
stays validated by the existing scripted engine tooling.

