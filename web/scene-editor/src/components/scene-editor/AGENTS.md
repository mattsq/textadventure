# Scene Editor Feature Components Guide

## Scope
These rules apply to every file under `web/scene-editor/src/components/scene-editor/`.

## Implementation Notes
- Keep components focused on orchestrating editor workflows (choices, transitions, dialogs) while remaining controlled by props. Business logic for persistence or store mutations should live in hooks/state slices.
- Prefer immutable updates when transforming lists passed through callbacks (`onMoveChoice`, `onRemoveChoice`, etc.) and surface typed payloads so callers can reuse them in Zustand actions.
- Compose UI from primitives in `../display` and `../forms` to ensure styling, spacing, and validation feedback stays consistent across the editor.
- Guard expensive derived data with `React.useMemo`/`useCallback` as demonstrated in existing components to prevent unnecessary re-renders when parents update frequently.
- Whenever a component introduces asynchronous states or status copy, synchronise wording with the validation terminology defined in `src/state` to avoid diverging UX language.
