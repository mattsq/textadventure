# React Scene Editor Overview

## Product Vision
The scene editor enables designers, writers, and playtesters to build interactive
story content without touching Python runtime code. It provides a focused
workspace for authoring locations, actors, branching narrative beats, and
interaction logic that can be exported directly into the `textadventure`
runtime. The editor emphasizes:

- **Narrative fidelity** – guardrails keep scene structure and speaker metadata
  consistent with backend schema expectations.
- **Rapid iteration** – inline previews, diff-friendly exports, and persistent
  drafts accelerate feedback cycles between writers and developers.
- **Collaboration** – presence indicators and shared workspaces make it easy for
  multidisciplinary teams to contribute simultaneously.

## Editor Surface & Navigation Model
The scene editor is organised around three primary surfaces:

1. **Project Dashboard** – entry point listing available adventures, recent
   edits, and quick links to shared documentation. This page wires into the
   backend session catalogue API and exposes entry points for creating or
   importing scene collections.
2. **Scene Workspace** – the primary canvas for editing locations, dialogue
   nodes, and branching paths. It contains:
   - A **graph canvas** for visualising node connectivity and traversal rules.
   - A **detail side panel** for editing node metadata, triggers, and outcomes.
   - Inline **transcript previews** that display how authored content will play
     inside the runtime.
3. **Collaboration Hub** – contextual tools for co-editing, including live
   cursors, comment threads, and change history playback.

Primary navigation lives in the left rail. Each rail item maps to a React route
(see `docs/react_scene_editor_structure.md`) and loads a lazily bundled feature
module. Route transitions persist the currently loaded project state so authors
can swap between editing modes without losing unsaved changes.

## Core User Journeys
Typical flows supported by the editor include:

- **Author a new scene** – create a blank scene, define starting nodes, attach
  characters, and preview the narrative path before publishing.
- **Extend an existing storyline** – clone or branch from an existing node,
  adjust dialogue, and verify triggers against the world state requirements.
- **Validate scene integrity** – run schema checks, identify orphaned nodes,
  and align metadata with runtime expectations prior to export.
- **Collaborate on revisions** – request review, leave inline comments, and
  resolve discussion threads while iterating on the same scene graph.

## Backend Integration
The frontend communicates with the Python backend through a small set of REST
and websocket endpoints defined in `docs/web_editor_api_spec.md`.

- **Session & Project APIs** – provide lists of available projects, handle
  creation of new adventures, and manage locking semantics so that concurrent
  edits do not collide.
- **Scene Graph APIs** – fetch and persist node graphs in the format described in
  `docs/web_editor_schema.md`. Payloads include graph topology, node metadata,
  conditional logic, and localisation bundles.
- **Collaboration APIs** – websocket channels broadcast presence, comment
  activity, and cursor positions. Event envelopes conform to the shared
  `CollaborationEvent` schema consumed by the frontend store.

All API interactions flow through the `sceneEditorApi` client module, which is
wrapped by React Query hooks for data fetching and caching. These hooks emit
loading and error states consumed by layout components to display skeletons or
inline alerts. Mutations automatically invalidate related cache keys so that
state stays consistent across tabs.

## State Management & Persistence
The editor uses a layered state model:

- **Server state** handled by React Query tracks authoritative scene data and
  synchronises changes with the backend.
- **Client state** within Zustand stores records transient UI selections (active
  node, zoom level, drawer visibility) without triggering global re-renders.
- **Form state** managed by React Hook Form powers the detail panel, ensuring
  validations mirror backend schema constraints.

Autosave runs on a debounced timer and upon explicit publish actions. Failed
mutations surface toast notifications and enqueue retries, while conflict
responses prompt users to merge upstream changes via the change history modal.

## Extensibility & Future Work
As new storytelling capabilities emerge (e.g., procedural content, LLM-assisted
writing), the editor is designed to accommodate modular feature toggles. Shared
component primitives documented in `docs/frontend_component_catalog.md`
(placeholder) provide consistent visual language and accessibility patterns.
Future enhancements under consideration include:

- Draft/preview workflows for testing scenes against branching analytics.
- Rich diff visualisations that compare scene versions across commits.
- Plugin points for custom validation rules specific to hosted adventures.

