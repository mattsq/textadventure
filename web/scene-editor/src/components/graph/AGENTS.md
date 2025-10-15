# Scene Editor Graph Components Guide

## Scope
These rules apply to every file under `web/scene-editor/src/components/graph/`.

## Implementation Notes
- Build graph primitives as React Flow node/edge renderers. Accept `NodeProps`/`EdgeProps` and keep them pure—state updates and store access belong in the caller that composes the graph.
- Preserve keyboard and screen-reader affordances on interactive elements (e.g. focusable nodes, `onKeyDown` handlers mirroring click behaviour, descriptive tooltips).
- Derive colours and effects from the existing variant maps (`sceneValidationClasses`, `variantAccentClasses`, badge tones) instead of introducing ad-hoc Tailwind tokens.
- Keep helpers like `buildBadges` and `classNames` local to the module unless they become broadly reusable; document any new graph variants in the file for future maintainers.
- Re-export additional graph renderers through `index.ts` so the routing layer imports remain consistent.
