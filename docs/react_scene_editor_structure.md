# React Scene Editor Structure and Integration Notes

This document captures the current layout of the React-based scene editor shipped under `web/scene-editor/`, including routing, component groupings, state management, and backend integration seams. It serves as a reference for contributors who need to understand the existing UI scaffolding before extending the editor.

## Routing Overview
- `App.tsx` mounts a `BrowserRouter` with nested routes for the overview (`/`), scene library (`/scenes`), scene graph (`/graph`), creation wizard (`/scenes/new`), and scene detail (`/scenes/:sceneId`) views, plus a wildcard redirect to the overview.
- `routes/SceneEditorLayout.tsx` provides the shared shell (breadcrumbs, navigation tabs, sidebar onboarding copy, and navigation log banner) that wraps each routed page.

## Component Groups
- `components/layout/` exposes primitives such as `EditorShell`, `EditorHeader`, `EditorSidebar`, and `EditorPanel` to keep page chrome consistent.
- `components/navigation/` contains reusable `Breadcrumbs` and `Tabs` widgets with keyboard focus styling and ARIA labels.
- `components/display/` bundles data presentation helpers (badges, cards, tables, validation indicators, metadata cells) that rely on Tailwind utility classes for dense dashboard styling.
- `components/forms/` wraps shared input scaffolding such as `FormField`, `TextField`, `SelectField`, and `TextAreaField` to maintain uniform spacing and labeling across forms.
- `components/graph/` includes lightweight SVG-based `SceneGraphNode` and `SceneGraphEdge` renderers that will consume backend topology data once the visualization is complete.
- `components/scene-editor/` contains task-specific widgets like `ChoiceListEditor`, `TransitionListEditor`, and `SceneDeletionDialog` that orchestrate state mutations via the store and API client.
- `components/collaboration/` provides the polling-based `CollaboratorPresenceIndicator` to surface live editing sessions with role-specific badge variants.

## State and API Layers
- `state/sceneEditorStore.ts` centralises editor UI state with Zustand, exposing tab selection, scene table queries, deletion workflows, and navigation log updates alongside async loaders that depend on the API client.
- `api/client.ts` defines the REST contracts (`SceneSummary`, transition resources, collaboration sessions, graph payloads) plus an error wrapper consumed by the store and routed pages through `createSceneEditorApiClient`.

## Backend Integration Seams
- The scene library view consumes `createSceneEditorApiClient` to fetch paginated `SceneSummary` collections, mirroring the FastAPI `SceneListResponse` schema in `src/textadventure/api/app.py`.
- Graph components expect `SceneGraphNodeResource` and `SceneGraphEdgeResource` payloads that align with the backend graph endpoints defined in the FastAPI app.
- Deletion dialogs and collaboration indicators rely on reference lookups and session listings surfaced through `SceneReferenceListResponse` and `ProjectCollaborationSessionListResponse`, which in turn map to backend utilities for transition inspection and collaborator tracking.

## Shared Assumptions
- Layout copy and store defaults assume the backend publishes validation status (`valid`/`warnings`/`errors`), transition counts, and last-updated timestamps for each scene, matching fields present in the Python `SceneSummary` model.
- The navigation log and tab state rely on deterministic string keys so backend-triggered updates (e.g., after a mutation) can append fresh log messages without disturbing existing UI copy.
- Collaboration polling assumes stable project identifiers and optional scene focus markers, matching the backend session tracker contract under `ProjectCollaborationSessionResource` and heartbeat TTL expectations in the FastAPI app.
