# Scene Editor Navigation Components Guide

## Scope
These rules apply to every file under `web/scene-editor/src/components/navigation/`.

## Implementation Notes
- Render navigation primitives with semantic HTML (`nav`, `ol`, `button`/`a`) and matching ARIA attributes (`aria-current`, roving tab index) to keep keyboard interactions predictable.
- Keep components controlled by props; they should not read editor state directly. Notify consumers of selection changes through typed callbacks.
- Follow the established focus ring and spacing utilities so navigation surfaces align with the broader design system.
- When adding routes or tab definitions, export string literal union types to preserve autocomplete and prevent mismatched labels.
- Update `index.ts` whenever new navigation primitives become available so screens continue importing from the barrel.
