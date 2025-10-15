# Scene Editor Display Components Guide

## Scope
These rules apply to every file under `web/scene-editor/src/components/display/`.

## Implementation Notes
- Keep components presentational and side-effect free. They should receive data through props and never talk directly to stores or APIs.
- Preserve accessible semantics used today: tables require captions and keyed rows, status indicators need `aria-hidden`/text alternatives, and headings must remain in the document flow.
- Extend established variants (`CardVariant`, badge tones, dense table modes) rather than introducing ad-hoc styling flags. If a new appearance is needed, document it alongside its design intent.
- Compose styles with Tailwind utility classes and the shared `classNames` helpers—avoid bespoke CSS files or magic colour values.
- When adding exports, update `index.ts` so downstream imports continue to resolve through the aggregated barrel.
