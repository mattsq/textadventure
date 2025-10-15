# Scene Editor Collaboration Components Guide

## Scope
These rules apply to every file under `web/scene-editor/src/components/collaboration/`.

## Implementation Notes
- Fetch remote data through `createSceneEditorApiClient` and reuse the typed resources from `src/api`; avoid duplicating request logic in multiple components.
- Model async behaviour with discriminated unions like `PresenceState` so loading/error/disabled states remain explicit and serialisable.
- Keep polling intervals and other timers configurable constants to simplify future tuning and unit testing.
- When rendering live presence, surface both textual labels and colour-coded badges as shown in `CollaboratorPresenceIndicator` so the UI remains accessible to screen readers and colour-blind users.
- Re-export new collaboration widgets from `index.ts` to maintain a consistent import surface for screens that compose collaboration features.
