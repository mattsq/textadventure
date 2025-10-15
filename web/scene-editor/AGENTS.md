# Scene Editor Frontend Contributor Guide

## Scope
These rules apply to every file under `web/scene-editor/`.

## General Workflow
- Install dependencies with `npm install` and keep lockfiles up to date.
- Before committing frontend changes run `npm run typecheck` and `npm run build` to mirror CI expectations.
- Capture or update screenshots when a change alters rendered UI.

## TypeScript & React Conventions
- Use modern function components. Prefer named exports; reserve default exports for top-level route elements consumed by the router.
- Keep prop and state types explicit. When extending shared data models add or reuse types from `src/api` or `src/state` instead of introducing untyped objects.
- Continue the "readonly-first" style used throughout the project: favour `readonly` properties and `as const` tuples for fixed options.
- Co-locate lightweight helpers (formatters, constants) with the component that uses them, but extract reusable building blocks into domain directories under `src/components/`.

## Styling Practices
- Compose layouts with Tailwind utility classes. New global styles belong in `src/index.css`; avoid additional CSS files unless coordinated with maintainers.
- Reuse existing design tokens (spacing, colours, typography) from `tailwind.config.js` and prefer semantic class names (e.g., `text-muted`, `bg-surface`) when available.

## State Management
- Use the Zustand store in `src/state/` for editor-wide state. Add new slices/actions via dedicated files that export both types and setters, keeping state updates immutable.
- When adding async flows, update the `AsyncState` status fields consistently (`"idle" → "loading" → "success"/"error"`) and capture timestamps via `new Date().toISOString()` as established in `sceneEditorStore`.
- Record user-facing log messages whenever state changes materially affect the editor so history panels remain informative.

## API Usage
- Instantiate API clients through `createSceneEditorApiClient` and centralise fetch logic in hooks or store actions rather than components.
- Catch `SceneEditorApiError` and surface actionable feedback (status codes, messages) to the UI; fall back to generic copy only when the error type is unknown.
- Ensure request payloads and responses stay aligned with the typed contracts defined in `src/api/client.ts`. Update both the types and any dependent selectors when the backend schema evolves.

## File Organisation
- Place page-level screens under `src/pages/` and wire them through `src/routes/`. Shared UI primitives belong in the appropriate domain-specific folder under `src/components/`.
- For new feature areas create a nested `AGENTS.md` describing additional rules (forms, graph, collaboration, etc.) once the directory gains specialised patterns.
