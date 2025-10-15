# React Scene Editor Documentation Audit

## Scope
This audit covers repository guidance relevant to the Vite + React scene editor, focusing on existing instructions, documentation coverage, and mismatches between the documented backend contracts and the current frontend implementation.

## Instruction Inventory
- **Root `Agents.md`** – Establishes general repository workflows (Python-first quality gates, formatting/linting expectations) but does not mention npm commands, Vite development workflows, or screenshot guidance for frontend changes.
- **`TASKS_DOCS.md`** – Provides a phased plan for expanding React editor documentation; no scoped AGENTS files currently exist under `web/scene-editor/`.

## Documentation Coverage
- Backend-leaning references dominate `docs/` (architecture, runtime APIs, analytics). Files such as `docs/web_editor_api_spec.md` and `docs/web_editor_schema.md` describe REST and JSON contracts but stop short of explaining React project setup, routing, or component patterns.
- No document currently introduces the Vite tooling stack, npm scripts, Tailwind usage, or the structure under `web/scene-editor/src/`.
- Component-level behaviour (forms, graph visualisation, scene editing primitives) is undocumented, leaving future contributors without guidance on props, state flows, or accessibility expectations.

## Identified Divergences Between Docs and Implementation
- The API client in `web/scene-editor/src/api/client.ts` expects project, collaboration session, validation summary, graph, and import endpoints plus versioning metadata (`version_id`, `checksum`), none of which are described in `docs/web_editor_api_spec.md` (which focuses solely on scene CRUD operations).
- Frontend types model response envelopes that include validation issue arrays on read/write operations, whereas `docs/web_editor_schema.md` only captures the base JSON scene structure without version metadata or validation payloads.
- The editor’s API layer normalises base URLs and query parameters for pagination/search beyond what the current docs prescribe, suggesting expanded filtering semantics that are undocumented.

## Next Steps
- Draft scoped AGENTS guidance for `web/scene-editor/` covering React/Vite workflows, npm commands, and screenshot expectations.
- Expand `docs/web_editor_api_spec.md` (or companion documents) to document the additional endpoints and metadata expected by the frontend.
- Author a React-specific overview that maps routing, state management, and component groups, then link it from the root contributor guides.
