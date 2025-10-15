# Scripted Scene Schema Relationships

This note distils the implicit data model behind
`textadventure/data/scripted_scenes.json`. It is intended to give the future web
editor a precise view of how the existing runtime links scenes, transitions,
items, and history requirements so that the API design can mirror those
relationships.

## Top-Level Structure

Scene files are JSON objects whose keys are **scene identifiers**. Each entry is
a scene definition containing three primary fields:

- `description` – Base narration shown when the player arrives in the scene.
- `choices` – Ordered list of available commands, each with a human friendly
  `description`.
- `transitions` – Mapping from command string to the transition definition that
  executes when that command is entered.

```mermaid
erDiagram
    Scene ||--o{ Choice : presents
    Scene ||--o{ Transition : exposes
```

Scene identifiers are globally unique within the file because transitions refer
to them via the `target` field.

## Choices

A choice is a lightweight object with two required strings: `command` and
`description`. Commands are unique within a scene and case-insensitive at
runtime. Choices do **not** encode any outcomes themselves—the matching
transition is responsible for all state changes and narration.

```json
{
  "command": "unlock",
  "description": "Use the brass key on the gate."
}
```

## Transitions

A transition bundles the consequences of entering a command. Every transition
must provide a `narration` string and can optionally specify:

- `target` – Destination scene identifier. `null` keeps the player in place.
- `item` – Inventory item awarded on success (one-time per playthrough).
- `requires` – Inventory items needed for success. Missing items trigger either
  the `failure_narration` or a default reminder and the scene does not change.
- `consumes` – Inventory items removed after a successful transition.
- `records` – History entries appended to the player's journal when the
  transition succeeds.
- `narration_overrides` – Ordered list of conditional narration blocks (see
  below).

```mermaid
erDiagram
    Transition }o--|| Scene : target
    Transition }o--o{ Item : grants
    Transition }o--o{ Item : requires
    Transition }o--o{ Item : consumes
    Transition }o--o{ HistoryRecord : writes
```

The runtime resolves all `target` identifiers up front and rejects unknown
references. This makes `Transition.target` a many-to-one relationship pointing
at a valid `Scene`.

### Inventory Semantics

Inventory interactions happen through three disjoint lists:

- `item` → adds exactly one copy of the named item (idempotent).
- `requires` → set of items that must already be present.
- `consumes` → items removed from the inventory when the transition succeeds.

Transitions can simultaneously award and consume different items to model
crafting recipes.

### History Records

History entries (produced via `records`) are opaque strings stored on the world
state's rolling log. They are later queried by conditional narration blocks and
other analytics. The engine never deletes history entries.

## Conditional Narration Overrides

Each entry in `narration_overrides` replaces the base `narration` when all of its
filters pass. Overrides are evaluated in order until the first match succeeds.
Available filters mirror the world state's inventory and history and support
both positive and negative checks:

- `requires_history_all`, `requires_history_any`
- `forbids_history_any`
- `requires_inventory_all`, `requires_inventory_any`
- `forbids_inventory_any`

Overrides can also emit additional `records` if they are the selected branch.

```json
{
  "narration": "The gate clicks open.",
  "requires_history_any": ["Studied the gate glyphs"],
  "forbids_inventory_any": ["rusty-key"],
  "records": ["Opened gate with knowledge"]
}
```

The override schema is intentionally parallel to the top-level transition fields
so the editor can reuse validation logic and UI components across both layers.

## Derived Relationships

To support analytics and validation, the runtime computes additional derived
relationships from the scene definitions:

- **Item flow** – A given item may have multiple sources (transitions with
  `item`), requirements (`requires` lists), and consumption sites (`consumes`
  lists). These relationships are surfaced in
  `textadventure.analytics.analyse_item_flow` for reporting.
- **Scene graph** – Directed edges are formed by every transition with a
  non-null `target`. Reachability analyses such as
  `textadventure.analytics.compute_scene_reachability` walk this graph.
- **History usage** – Both transitions and overrides append to the world state's
  history via `records`, while overrides read from the history to gate
  narration. Designing APIs or UI affordances should treat history entries as
  free-form identifiers referenced across scenes.

Understanding these relationships will help the web editor surface impact
analysis (e.g., "deleting this scene breaks 3 transitions" or "this item is
consumed but never awarded") and mirror the runtime's validation guarantees.

## Dataset Envelope and Version Metadata

While the runtime continues to load a flat `{ scene_id: SceneResource }`
mapping, the editor-oriented API wraps those definitions in an envelope that
adds bookkeeping information for backups, collaboration, and optimistic
concurrency. Exports and import previews share the following structure:

```json
{
  "generated_at": "2024-07-05T08:00:00Z",
  "schema_version": 2,
  "start_scene": "village-square",
  "version_id": "20240705T080000Z-1a2b3c4d",
  "checksum": "f3a8…",
  "scenes": { /* Mapping of scene ids to SceneResource definitions */ }
}
```

- **`generated_at`** – ISO 8601 timestamp describing when the dataset was
  produced. UIs display it in confirmation prompts and audit logs.
- **`schema_version`** – Positive integer describing the structural revision of
  the payload. The API migrates older versions forward before diffing or
  validating them.
- **`start_scene`** – Optional canonical entry scene for reachability analysis.
- **`version_id`** – Server-generated identifier used for optimistic concurrency
  checks (`base_version_id` in write requests) and for naming exported archives.
- **`checksum`** – SHA-256 digest of the canonical scene ordering so that
  clients can detect accidental corruption or reordering.
- **`scenes`** – The authoritative scene definitions described earlier in this
  document.

The same envelope appears inside branch planning, rollback previews, and project
exports. When tooling stores local drafts it should persist these metadata
fields alongside the scene definitions so that re-synchronisation with the API
remains reliable.

## Validation Report Shape

Validation responses bundle multiple analyses so that editors can render rich
feedback without issuing additional requests. The TypeScript-style definition
below captures the composite structure emitted by import previews, validation
endpoints, and write responses:

```ts
type ReachabilityReport = {
  start_scene: string;
  reachable_count: number;
  unreachable: string[];
};

type ItemFlowReport = {
  items: {
    id: string;
    awarded_by: string[];
    required_by: string[];
    consumed_by: string[];
  }[];
};

type QualityReport = {
  issues: ValidationIssue[];
  summary: {
    error_count: number;
    warning_count: number;
  };
};

type ValidationReport = {
  generated_at: string;
  reachability: ReachabilityReport;
  item_flow: ItemFlowReport;
  quality: QualityReport;
};
```

When a scene passes validation the `issues` array may still include warnings for
lint-style checks (unused items, unreachable narration overrides, etc.). Editors
should block destructive actions only when `quality.summary.error_count > 0` but
are encouraged to surface warnings prominently.

## Schema Evolution and Compatibility

Schema version `1` mirrored the raw runtime JSON and assumed the consumer would
inject any metadata it required. Version `2`—the current draft used by the web
editor—introduces the dataset envelope, start-scene hint, validation reports,
and the `version_id`/`checksum` pair for synchronisation. Payloads declare their
version through the `schema_version` field; when omitted the API assumes the
latest revision and populates it during export so future imports retain the
information.

The backend maintains explicit migration helpers so that legacy datasets stay
compatible. If a payload declares a newer schema version than the server
understands, the API responds with a validation error listing the unsupported
version and inviting the operator to upgrade. Future revisions should extend the
changelog below with a short description and migration expectations.

## Changelog

- **2024-07-05 – Schema version 2 draft.** Added dataset envelope metadata
  (`generated_at`, `schema_version`, `start_scene`, `version_id`, `checksum`),
  formalised validation report shapes, and documented migration expectations for
  optimistic concurrency.
- **2024-03-15 – Initial extraction.** Captured the core relationships between
  scenes, choices, transitions, inventory, and history for the web editor
  planning effort.
