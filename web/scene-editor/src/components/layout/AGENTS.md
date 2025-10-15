# Scene Editor Layout Components Guide

## Scope
These rules apply to every file under `web/scene-editor/src/components/layout/`.

## Implementation Notes
- Treat layout primitives as structural wrappers: they orchestrate slots like header/sidebar/main content but should not fetch data or own business logic.
- Maintain the responsive flex/grid patterns already in use. Any new breakpoint behaviour must preserve editor usability on both desktop and narrow viewports.
- Offer composition via props (`header`, `sidebar`, `footer`, render props) instead of hard-coding concrete children.
- When exposing optional regions, guard them with conditional rendering just like `EditorShell` to avoid empty DOM nodes.
- Document new shells or panels in component JSDoc/comments so downstream teams understand intended usage.
