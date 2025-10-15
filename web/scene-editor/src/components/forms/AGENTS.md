# Scene Editor Form Components Guide

## Scope
These rules apply to every file under `web/scene-editor/src/components/forms/`.

## Implementation Notes
- Compose new fields with the shared `FieldWrapper` patterns used in `FormField.tsx` so labels, descriptions, and errors stay wired with matching `aria-*` IDs.
- Expose interactive controls through `React.forwardRef` when they render focusable elements. Accept `BaseFieldProps` alongside native element props so callers inherit the standard field API.
- Mirror the accessibility affordances established here: controlled inputs, combobox/listbox roles, keyboard handlers, and `aria-invalid`/`aria-describedby` flags must remain consistent.
- Style controls by extending the existing utility builders (e.g. `buildControlClassName`) and Tailwind tokens. Avoid introducing bespoke CSS or inline hex colours.
- Re-export any new primitives from `index.ts` to keep the module surface stable for other feature areas.
