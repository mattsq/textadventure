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
  - `requires` (array of strings, optional) – List of inventory items the
    player must currently hold for the transition to succeed. When any items
    are missing the engine narrates either the provided `failure_narration` or
    a default reminder and leaves the player in the current scene.
  - `failure_narration` (string, optional) – Custom narration used when
    `requires` checks fail.
  - `consumes` (array of strings, optional) – Items to remove from the
    inventory when the transition succeeds. This is useful for crafting steps
    where reagents combine into a new item granted via `item`.
  - `records` (array of strings, optional) – Extra journal entries to append
    to the `WorldState` history after the transition succeeds. Use this to log
    achievements or milestones that future scenes can reference.
  - `narration_overrides` (array of objects, optional) – Ordered list of
    conditional narration hooks. Each override must provide a replacement
    `narration` string plus any combination of the following filters:
    - `requires_history_all` / `requires_history_any` – History entries that
      must already exist before the override can trigger.
    - `forbids_history_any` – History entries that must not be present.
    - `requires_inventory_all` / `requires_inventory_any` – Inventory checks
      that mirror the semantics of `requires` but without blocking the
      transition.
    - `forbids_inventory_any` – Inventory items that prevent the override from
      activating when held.
    - `records` – Additional history entries written only when the override is
      selected.
    The first override whose filters match the current world state will be
    used; remaining overrides are ignored. When no overrides match the engine
    falls back to the base `narration` text.

Commands listed in `choices` should have matching entries in `transitions`
unless the command is handled by the story engine directly (see the "Built-in
Commands" section below). The validation helpers in
`textadventure.scripted_story_engine.load_scenes_from_mapping` raise descriptive
errors if required fields are missing, commands are duplicated, or transitions
reference unknown targets.

When using `requires`, remember that item names are compared literally against
the player's inventory. For readability, keep item names consistent between
the `item`, `requires`, and `consumes` fields.

### Conditional Narration Example

The ranger lookout scene demonstrates how overrides can tailor narration based
on prior events:

```json
"signal": {
  "narration": "You attempt to recall the ranger's cadence, but without proper guidance the notes unravel before the finale.",
  "narration_overrides": [
    {
      "requires_history_any": ["Picked up signal lesson"],
      "narration": "You practice the cadence until the surrounding woods echo the final note back to you.",
      "records": ["Practiced the ranger signal"]
    }
  ]
}
```

Before the player completes the `train` command the base narration communicates
that they still need guidance. Once the history contains `Picked up signal
lesson` the override fires, swapping in the celebratory narration and logging a
`Practiced the ranger signal` milestone for later scenes to reference.

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

## Expanded Demo Reference

The JSON file now ships with the full expanded storyline. Use the following
overview to orient yourself when authoring additional content or planning
playtests.

### Region Map

```
Forest Approach
  starting-area ─┬─> old-gate ──> misty-courtyard ─┬─> collapsed-hall ─┬─> sealed-crypt
                 │                                 │                   └─> (loot + lore)
                 ├─> scavenger-camp                ├─> flooded-archives
                 └─> ranger-lookout                └─> echoing-stair ──> aether-spire-base
                                                                       ├─> astral-workshop
                                                                       ├─> chronicle-chamber
                                                                       └─> celestial-observatory ──> resonant-bridge ──> sky-sanctum
```

- **Forest Approach** introduces navigation, the lore `guide`, and optional
  pickups that ease later puzzles. Both detours return to the trailhead so
  players can collect the **rusty key**, **weathered map**, and **signal lesson**
  in any order.
- **Sunken Bastion** forms the mid-game hub. `misty-courtyard` branches toward
  the `collapsed-hall` lock, the treasure-rich `flooded-archives`, and the
  `echoing-stair` transition to the finale. The `sealed-crypt` rewards careful
  preparation with the **ancient sigil**.
- **Aether Spire** resolves the quest. The base connects optional side rooms to
  gather crafting materials before the `celestial-observatory` ending.

### Quest Flow Summary

1. **Trailhead Orientation** – Establish the expedition objective at
   `starting-area`, prompt players to try `guide`, and highlight the gate.
2. **Courtyard Access** – Collect the **rusty key** and learn the ranger
   `signal` so `collapsed-hall` and `sealed-crypt` become reachable. Optional
   items like the **weathered map** enrich lore scenes but are not required to
   progress.
3. **Bastion Investigation** – Alternate between the `flooded-archives` (for the
   **sunstone lens**) and hall/crypt chain (for the **echo shard** and **ancient
   sigil**). Reinforce memory mechanics by encouraging use of `journal` and
   `recall` between excursions.
4. **Spire Preparation** – Use the `astral-workshop` to convert the **echo
   shard** and **luminous filament** into the **resonant chime**, and visit the
   `chronicle-chamber` for optional exposition when carrying the **weathered
   map**.
5. **Observatory Finale** – Combine the **sunstone lens** and **resonant chime**
   at the `celestial-observatory` to open the resonant bridge toward the
   sanctum. Players who skipped optional objectives receive tailored failure
   narration nudging them toward outstanding tasks.
6. **Sanctum Resolution** – Cross the `resonant-bridge` with the **ancient
   sigil** and stabilise the `sky-sanctum` using the crafted chime to conclude
   the storyline and record the final history beat.

### Authoring Tips for Further Expansion

- **Add regional spokes** by following the established pattern: a hub scene with
  multiple outward transitions, each returning the player to regroup before
  advancing deeper.
- **Layer optional rewards** that interact with existing mechanics. Lore items
  (like the **weathered map**) can unlock new tool prompts or augment
  `journal`/`recall` flavour without blocking core progress.
- **Telegraph locks clearly** using `failure_narration` so players understand
  which items or lessons they need and where to find them.
- **Reuse crafted items** by combining `requires` and `consumes`. The workshop
  chain demonstrates how to consume reagents yet leave the resulting tool
  available for later checks.
- **Document new branches** in this guide as you extend the map so playtesters
  and fellow authors can follow the evolving structure at a glance.
