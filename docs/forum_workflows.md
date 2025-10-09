# Forum Workflows

This guide explains how the discussion forum feature exposed by the scene editor
API works, how to enable it in local deployments, and what requests clients
should issue to create, browse, and reply to threads. It is aimed at both scene
authors who want to collaborate through the forum endpoints and contributors who
plan to extend the implementation.

## Enabling the forum service

The forum APIs are bundled with the FastAPI application returned by
`textadventure.api.create_app`. By default the service persists threads beneath a
`forums/` directory relative to the current working directory, so no additional
configuration is required for quick experiments. For explicit control set the
`TEXTADVENTURE_FORUM_ROOT` environment variable (or pass
`SceneApiSettings(forum_root=...)` when creating the app) to point at the
desired storage directory. Each thread is stored as a prettified JSON document,
so the backing directory can be placed under version control for moderation or
backups.【F:src/textadventure/api/app.py†L2900-L2979】【F:src/textadventure/api/settings.py†L28-L76】

```
export TEXTADVENTURE_FORUM_ROOT=/srv/textadventure/forums
uvicorn textadventure.api.server:app --reload
```

With the environment variable exported, the FastAPI app automatically wires a
`ForumStore` and `ForumService` that operate on the configured location. No
additional CLI flags or feature gates are required.【F:src/textadventure/api/app.py†L6524-L6600】

## Data model overview

Forum content is stored as individual JSON files whose names correspond to the
thread identifier (e.g., `character-concepts.json`). Each payload captures the
thread metadata plus an ordered list of posts:

```json
{
  "id": "character-concepts",
  "title": "Character concepts",
  "author": "Nova",
  "created_at": "2024-06-01T12:00:00+00:00",
  "updated_at": "2024-06-01T12:45:12+00:00",
  "posts": [
    {
      "id": "89f8b56af2a84ffab6e41092f6f7c2ad",
      "author": "Nova",
      "body": "Share your favourite hero archetypes.",
      "created_at": "2024-06-01T12:00:00+00:00"
    },
    {
      "id": "1b7d00cc98c44b2b9da804f4db7f1318",
      "author": "Rowan",
      "body": "I like foils that contrast the main party.",
      "created_at": "2024-06-01T12:45:12+00:00"
    }
  ]
}
```

Identifiers are slugified lower-case strings containing letters, numbers, and
hyphens. Clients may supply a custom identifier when creating a thread; otherwise
the service derives one from the title and appends numeric suffixes as needed to
avoid collisions.【F:src/textadventure/api/app.py†L3144-L3300】【F:src/textadventure/api/app.py†L4640-L4666】

## User workflows

Once the API server is running, authors can interact with the forum via the
following REST endpoints. All payloads are JSON and timestamps are returned in
ISO 8601 UTC.

### List threads

```
GET /api/forums/threads?page=1&page_size=20
```

Returns paginated thread summaries ordered by most recent activity. Useful for
index views in the editor UI.【F:src/textadventure/api/app.py†L7670-L7684】

### Create a thread

```
POST /api/forums/threads
Content-Type: application/json
{
  "title": "Design feedback",
  "body": "Share your latest encounter ideas here.",
  "author": "Nova"
}
```

Creates a new thread using the body as the initial post. Optionally include an
`identifier` field to reserve a specific slug; otherwise one is generated.
Attempts to reuse an existing identifier return `409 Conflict`. The response body
contains the thread metadata plus the first post so clients can transition to a
thread detail view immediately.【F:src/textadventure/api/app.py†L7686-L7705】【F:tests/test_api_forum.py†L13-L39】

### Retrieve a thread

```
GET /api/forums/threads/{thread_id}
```

Fetches the full thread including all posts. Use this to power the thread detail
page or to refresh after posting new replies.【F:src/textadventure/api/app.py†L7707-L7721】

### Reply to a thread

```
POST /api/forums/threads/{thread_id}/posts
Content-Type: application/json
{
  "body": "Consider foreshadowing with recurring motifs.",
  "author": "Quinn"
}
```

Appends a reply and returns the newly created post resource. Thread metadata is
updated so subsequent list/detail requests reflect the new activity timestamps
and post counts.【F:src/textadventure/api/app.py†L7722-L7736】【F:tests/test_api_forum.py†L41-L68】

## Contributor notes

- **Validation** – Title and body fields must be non-empty strings. Author names
  are optional but, when provided, are trimmed to avoid storing whitespace-only
  values. Identifier slugs are validated both at the API layer and when loading
  persisted documents.【F:src/textadventure/api/app.py†L1014-L1092】【F:src/textadventure/api/app.py†L3009-L3117】
- **Pagination** – `ForumService.list_threads` slices results in-memory after
  sorting by last activity. Adjust the storage backend if the forum grows beyond
  a handful of JSON files.【F:src/textadventure/api/app.py†L3138-L3183】
- **Testing** – `tests/test_api_forum.py` demonstrates end-to-end thread creation
  and reply flows using `TestClient`. Extend this module when adding new fields
  or behaviours.【F:tests/test_api_forum.py†L1-L68】

