# Data-Driven Scene Authoring

The demo adventure bundled with this repository loads its locations from
`textadventure/data/scripted_scenes.json`. This document explains how those
files are structured so designers can create new adventures or remix the demo
without editing Python code.

## File Overview

Scene files are UTF-8 encoded JSON documents. The top-level object maps each
location identifier to a scene definition:

```json
{
  "starting-area": { "description": "...", "choices": [...], "transitions": {...} },
  "old-gate": { "description": "...", "choices": [...], "transitions": {...} }
}
```

Location identifiers become the values returned by
`WorldState.location`. They can include lowercase letters, numbers, and
hyphen/underscore characters; choose names that make it easy to understand the
world map at a glance.

## Scene Fields

Each scene definition must provide the following keys:

- `description` (string) – Narrative text shown when the player first enters
  the scene or asks for the available choices again.
- `choices` (array) – List of objects describing the commands shown to the
  player. Each entry requires:
  - `command` (string) – The word the player types to trigger the choice. Input
    comparisons are case-insensitive, but it is conventional to keep commands
    lowercase when authoring.
  - `description` (string) – Short blurb summarising what the command does.
- `transitions` (object) – Mapping of command strings to the consequences of
  choosing them. Every transition supports the following keys:
  - `narration` (string, required) – Text that is narrated after the player
    enters the command.
  - `target` (string, optional) – Location identifier to move the player to
    after the narration. This must match another scene key in the same file.
  - `item` (string, optional) – Inventory item to grant the player. The
    `WorldState` ensures the item is only added once, even if the scene is
    replayed.

Commands listed in `choices` should have matching entries in `transitions`
unless the command is handled by the story engine directly (see the "Built-in
Commands" section below). The validation helpers in
`textadventure.scripted_story_engine.load_scenes_from_mapping` raise descriptive
errors if required fields are missing, commands are duplicated, or transitions
reference unknown targets.

## Built-in Commands and Tools

`ScriptedStoryEngine` recognises several quality-of-life commands without
needing explicit `transitions` entries:

- `journal` – Prints the recent observation history tracked by `WorldState`.
- `inventory` – Summarises the player's inventory contents.
- `recall` – Lists the player's recent actions.

The engine also supports pluggable tools. The bundled configuration maps the
`guide` command to `KnowledgeBaseTool`, allowing lore lookups such as `guide
forest`. When designing new adventures you can keep these commands, add your
own tool bindings, or remove them entirely by adjusting the tool mapping passed
to `ScriptedStoryEngine`.

## Linking Scenes

Transitions that include a `target` move the player into the referenced scene
and immediately narrate that scene's `description`. This makes it easy to
create branching paths:

```json
"forest-clearing": {
  "description": "Sunlight pours into the clearing...",
  "choices": [{ "command": "north", "description": "Follow the stream." }],
  "transitions": {
    "north": {
      "narration": "You follow the stream toward distant ruins.",
      "target": "ruined-aqueduct"
    }
  }
}
```

Ensure every `target` matches a scene key defined somewhere in the same file.
During loading, any unknown targets raise a validation error before the engine
is constructed.

## Loading Custom Scene Files

Use `textadventure.scripted_story_engine.load_scenes_from_file` to parse a
JSON scene file and pass the result into `ScriptedStoryEngine`:

```python
from textadventure import WorldState
from textadventure.scripted_story_engine import (
    ScriptedStoryEngine,
    load_scenes_from_file,
)

scenes = load_scenes_from_file("my_custom_adventure.json")
engine = ScriptedStoryEngine(scenes=scenes)
world = WorldState()
print(engine.propose_event(world).narration)
```

You can integrate custom scenes into the CLI by instantiating
`ScriptedStoryEngine` with your loaded mapping before passing it to
`MultiAgentCoordinator`. Designers can iterate quickly by editing the JSON file
and restarting the CLI without touching the engine implementation itself.
