# Documentation Expansion Plan – Task Tracker

This file tracks progress on the documentation improvements required for the React scene editor and related backend touchpoints.

## Phase 1 – Audit & Information Gathering
- [x] Inventory existing instructions (see `docs/react_editor_docs_audit.md`).
- [x] Map the frontend code structure and shared components.
  - Output: `docs/react_scene_editor_structure.md` summarises routing, component groups, and state/api layers.
- [x] Trace frontend ↔ backend integration seams and shared assumptions.
  - Notes captured alongside the structural summary in `docs/react_scene_editor_structure.md`.

## Phase 2 – Update Agent-Facing Guides
- [x] Revise the root `Agents.md` with frontend workflow expectations (npm scripts, testing, screenshot policy).
- [x] Create scoped guidance for the web editor in `web/scene-editor/AGENTS.md` (code style, state management, API usage).
- [x] Add nested `AGENTS.md` files for complex component directories to capture domain-specific rules.
  - Added scoped guides for `forms`, `display`, `layout`, `graph`, `scene-editor`, `navigation`, and `collaboration` component domains.

## Phase 3 – Expand Formal Documentation
- [x] Draft `docs/react_scene_editor_overview.md` describing product vision, page structure, and backend interactions. (Completed in v1 overview draft.)
- [x] Author `docs/frontend_component_catalog.md` detailing reusable components, props, and styling patterns. (Added sectioned catalog covering layout, display, forms, navigation, graph, scene workflows, and collaboration primitives.)
- [x] Refresh API/schema references (`docs/web_editor_api_spec.md`, `docs/web_editor_schema.md`) and introduce changelog sections.
  - Added dataset metadata envelopes, validation report breakdowns, and explicit changelog entries to align with schema version 2 plans.
- [ ] Update onboarding docs (`docs/getting_started.md`, `docs/contributing.md`) with unified Python + frontend setup instructions.

## Phase 4 – Create Maintenance Processes
- [ ] Define documentation ownership in `docs/best_practices.md` and add PR checklist updates.
- [ ] Evaluate automation options (CI checks for scoped `AGENTS.md`, docs spell-checker/link checker).
- [ ] Schedule recurring documentation audits and capture follow-up items in `TASKS.md` or future planning tools.

## Phase 5 – Knowledge Sharing & Examples
- [ ] Produce tutorial-style guides under `docs/tutorials/` covering end-to-end scene editing workflows.
- [ ] Expand `docs/architecture_overview.md` with rationale for the Vite + React + Tailwind stack and shared terminology definitions.
- [ ] Introduce PR narrative templates in `docs/contributing.md` for frontend-heavy work (screenshots, accessibility notes, state changes).

## Phase 6 – Continuous Feedback Loop
- [ ] Establish a feedback channel (survey or issue label) and reference it in `Agents.md` and `docs/contributing.md`.
- [ ] Outline a process for iterating on this plan after initial updates land, appending new tasks here as gaps surface.
