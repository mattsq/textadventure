# Scene Management API Specification

This document defines the initial RESTful API surface for the planned web-based
adventure editor. The goal is to expose CRUD operations for scripted scenes in a
way that mirrors the runtime data model and unlocks incremental editor features
(such as validation views, graph exploration, and analytics) without locking us
into premature implementation details.

The API is designed to sit in front of the existing JSON scene store described
in [`docs/web_editor_schema.md`](./web_editor_schema.md). All payloads are JSON.
Responses use UTF-8 encoding and snake_case field names to remain consistent
with the file format.

## Conventions

- **Base URL** – `/api`. All examples below omit the base.
- **Content negotiation** – Clients send `Accept: application/json` and, for
  write endpoints, `Content-Type: application/json`.
- **Authentication** – Deferred. The editor prototype will ship without auth,
  but the API is designed so auth headers can be layered in later without schema
  changes.
- **Error envelope** – Non-2xx responses follow a shared shape:

  ```json
  {
    "error": {
      "code": "validation_error",
      "message": "Readable summary for humans.",
      "details": [
        {
          "path": "transitions.open-gate.target",
          "message": "Target scene 'gate-courtyard' does not exist"
        }
      ]
    }
  }
  ```

- **Pagination** – Collection endpoints accept `page` and `page_size` query
  params. Defaults: `page=1`, `page_size=50`. Servers cap `page_size` at 200.
- **Timestamps** – Scene resources surface `created_at` and `updated_at` values
  in ISO 8601 UTC to support future auditing, even though the current JSON store
  does not persist them yet.

## Shared Data Structures

| Name | Description |
| --- | --- |
| `SceneSummary` | Lightweight representation for list views. Includes id, description snippet, counts, and validation status. |
| `SceneResource` | Full scene definition with nested choices and transitions. |
| `Choice` | `{ "command": "look", "description": "Examine the area." }` |
| `Transition` | Full transition payload mirroring the JSON schema. |
| `NarrationOverride` | Conditional narration entry evaluated before the base narration. |
| `ValidationIssue` | `{ "severity": "error", "code": "missing_target", "message": "…", "path": "…" }` |

Detailed schemas are provided below using TypeScript notation for readability.

```ts
// Shared enums
 type Severity = "error" | "warning";

type NarrationOverride = {
  narration: string;
  requires_history_all?: string[];
  requires_history_any?: string[];
  forbids_history_any?: string[];
  requires_inventory_all?: string[];
  requires_inventory_any?: string[];
  forbids_inventory_any?: string[];
  records?: string[];
};

type Transition = {
  narration: string;
  target: string | null;
  item?: string | null;
  requires?: string[];
  consumes?: string[];
  records?: string[];
  failure_narration?: string | null;
  narration_overrides?: NarrationOverride[];
};

type Choice = {
  command: string;
  description: string;
};

type SceneResource = {
  id: string;
  description: string;
  choices: Choice[];
  transitions: Record<string, Transition>;
  created_at: string;
  updated_at: string;
};

type SceneSummary = {
  id: string;
  description: string;
  choice_count: number;
  transition_count: number;
  has_terminal_transition: boolean;
  validation_status: "valid" | "warnings" | "errors";
  updated_at: string;
};

type ValidationIssue = {
  severity: Severity;
  code: string;
  message: string;
  path: string;
};
```

## Endpoints

### `GET /scenes`

List scenes for overview tables and navigation.

**Query parameters**

- `search` *(optional)* – Case-insensitive substring search over id and
  description.
- `updated_after` *(optional)* – ISO timestamp filter.
- `include_validation` *(optional)* – `true` to embed aggregated validation
  status (defaults to `true`).
- `page`, `page_size` – Standard pagination.

**Response – 200 OK**

```json
{
  "data": [
    {
      "id": "village-square",
      "description": "You stand in the heart of the village…",
      "choice_count": 3,
      "transition_count": 3,
      "has_terminal_transition": false,
      "validation_status": "warnings",
      "updated_at": "2024-03-18T12:34:56Z"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 50,
    "total_items": 120,
    "total_pages": 3
  }
}
```

### `GET /scenes/{scene_id}`

Fetch the canonical definition for a single scene.

**Path parameters**

- `scene_id` – Unique identifier.

**Query parameters**

- `include_validation` *(optional)* – `true` to append inline validation issues
  to the response (defaults to `false`).

**Response – 200 OK**

```json
{
  "data": {
    "id": "village-square",
    "description": "You stand in the heart of the village…",
    "choices": [
      { "command": "talk", "description": "Chat with the townsfolk." }
    ],
    "transitions": {
      "talk": {
        "narration": "Villagers share rumors about the forest.",
        "target": "forest-edge",
        "records": ["Spoke with villagers"]
      }
    },
    "created_at": "2024-03-10T09:12:00Z",
    "updated_at": "2024-03-18T12:34:56Z"
  },
  "validation": {
    "issues": []
  }
}
```

**Errors**

- `404 Not Found` – Scene id unknown.

### `GET /export/scenes`

Download the scripted scene dataset for offline editing, backup, or version
control. The response mirrors the JSON structure stored on disk, includes the
timestamp from the underlying resource, and now surfaces backup metadata that
helps with file naming and integrity verification.

**Query parameters**

- `ids` – Optional comma-separated list of scene identifiers to export. When
  omitted the entire dataset is returned. Unknown identifiers result in a
  `404 Not Found` response.
- `format` – Optional export formatting flag. Accepts `minified` (default) for
  compact output or `pretty` for indented JSON that is easier to review
  manually.

**Examples**

- `GET /export/scenes`
- `GET /export/scenes?ids=starting-area,forest-edge`
- `GET /export/scenes?format=pretty`

**Response – 200 OK**

```json
{
  "generated_at": "2024-03-18T12:34:56Z",
  "scenes": {
    "village-square": {
      "description": "You stand in the heart of the village…",
      "choices": [
        { "command": "talk", "description": "Chat with the townsfolk." }
      ],
      "transitions": {
        "talk": {
          "narration": "Villagers share rumors about the forest.",
          "target": "forest-edge",
          "records": ["Spoke with villagers"]
        }
      }
    }
  },
  "metadata": {
    "version_id": "20240318T123456Z-1a2b3c4d",
    "checksum": "0a1b2c3d4e5f67890123456789abcdef0a1b2c3d4e5f67890123456789abcdef",
    "suggested_filename": "scene-backup-20240318T123456Z-1a2b3c4d.json"
  }
}
```


### `POST /import/scenes`

Validate an uploaded dataset prior to applying it to the live store. The
endpoint performs structural validation, reachability analysis, and analytics
checks without mutating the bundled JSON file. It also accepts legacy
``schema_version`` payloads and migrates them to the current structure so older
editor exports remain compatible.

**Request body**

```json
{
  "scenes": { /* Mapping of scene ids to definitions */ },
  "schema_version": 1,
  "start_scene": "village-square"
}
```

**Fields**

- `scenes` *(required)* – Mapping of identifiers to scene definitions.
- `schema_version` *(optional)* – Positive integer indicating the schema the
  payload conforms to. When omitted it defaults to the current server version.
  Legacy datasets (currently version `1`) are migrated automatically. Requests
  specifying a newer schema version than the server supports result in a
  `400 Bad Request` response with a descriptive message.
- `start_scene` *(optional)* – Scene identifier to seed reachability
  calculations. Defaults to the first scene in the payload when omitted.

**Response – 200 OK**

```json
{
  "scene_count": 42,
  "start_scene": "village-square",
  "validation": {
    "generated_at": "2024-04-01T09:00:00Z",
    "reachability": {
      "start_scene": "village-square",
      "reachable_count": 42,
      "unreachable": []
    },
    "quality": { /* See validation report definition */ },
    "item_flow": { /* Item flow summary */ }
  }
}
```


### `POST /scenes`

Create a new scene. Requests provide the full scene payload except timestamps,
which are server-generated.

**Request body**

```json
{
  "id": "abandoned-hut",
  "description": "Dusty beams creak overhead…",
  "choices": [
    { "command": "search", "description": "Look for clues." }
  ],
  "transitions": {
    "search": {
      "narration": "You find a hidden compartment.",
      "item": "mysterious-map",
      "target": "forest-edge",
      "records": ["Found map in hut"]
    }
  }
}
```

**Responses**

- `201 Created`

  ```json
  {
    "data": {
      "id": "abandoned-hut",
      "created_at": "2024-03-20T08:00:00Z",
      "updated_at": "2024-03-20T08:00:00Z"
    },
    "links": {
      "self": "/api/scenes/abandoned-hut"
    }
  }
  ```

- `400 Bad Request` – Payload fails schema validation (invalid commands, missing
  fields, duplicate transitions, etc.). Returned using the shared error
  envelope with `code="validation_error"`.
- `409 Conflict` – Scene id already exists.

### `PUT /scenes/{scene_id}`

Replace the definition for an existing scene. Requests must include the full
scene payload. Partial updates are not supported (PATCH can be added later if
needed).

**Path parameters**

- `scene_id` – Identifier to replace. Must match `id` in the payload; mismatch
  triggers a `409` conflict to prevent accidental renames.

**Request body** – Same structure as `POST /scenes`.

**Responses**

- `200 OK`

  ```json
  {
    "data": {
      "id": "abandoned-hut",
      "created_at": "2024-03-20T08:00:00Z",
      "updated_at": "2024-03-21T15:30:00Z"
    }
  }
  ```

- `400 Bad Request` – Validation failure.
- `404 Not Found` – Unknown scene id.
- `409 Conflict` – Payload `id` does not match the path parameter.

### `DELETE /scenes/{scene_id}`

Remove a scene after verifying that no other scene depends on it. Clients can
request a dry-run impact report before committing the deletion.

**Query parameters**

- `force` *(optional)* – `true` to bypass dependency checks once the impact has
  been confirmed elsewhere. Defaults to `false`.
- `dry_run` *(optional)* – `true` to preview the impact without persisting the
  deletion. Defaults to `false`.

**Responses**

- `200 OK` – Deletion (or dry-run) succeeded.

  ```json
  {
    "data": {
      "deleted": true,
      "dependents": ["forest-edge"],
      "items_referenced": ["mysterious-map"]
    }
  }
  ```

  When `dry_run=true`, the response uses `"deleted": false` but returns the same
  dependency details so the UI can prompt for confirmation.

- `400 Bad Request` – `force=false` and dependencies exist. The error envelope's
  `details` array lists referencing scenes and transitions.
- `404 Not Found` – Unknown scene id.

## Validation Workflow

Although validation endpoints are covered by separate backlog items, the CRUD
API needs to surface enough metadata for the editor to warn authors early. The
plan is to run lightweight validation checks during `POST`/`PUT` and return the
issues inline. Comprehensive analyses (graph reachability, item flow, etc.) will
remain on the dedicated `/scenes/validate` endpoint once implemented.

Write operations therefore collect `ValidationIssue` instances and return them
alongside the persisted timestamps:

```json
{
  "data": {
    "id": "abandoned-hut",
    "created_at": "2024-03-20T08:00:00Z",
    "updated_at": "2024-03-21T15:30:00Z"
  },
  "validation": {
    "issues": [
      {
        "severity": "warning",
        "code": "unused_item",
        "message": "Item 'mysterious-map' is awarded but never required.",
        "path": "transitions.search.item"
      }
    ]
  }
}
```

Clients treat warnings as advisory but block saves when any `severity="error"`
issue appears.

## Notes for Future Iterations

- Introduce `PATCH /scenes/{scene_id}` for partial updates once concurrent edit
  scenarios surface.
- Provide `If-Match`/ETag headers to support optimistic concurrency.
- Extend `SceneSummary` with author attribution once authentication is added.
- Consider embedding derived analytics (reachability, item flow) behind an
  `include=` query flag to avoid redundant requests in the editor shell.
