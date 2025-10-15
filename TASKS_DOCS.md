# Documentation Expansion Plan for React Scene Editor

This plan outlines a comprehensive sequence of tasks to modernize repository guidance so future agents can ramp up quickly on the new Vite + React scene editor and its integration points with the Python runtime.

## Phase 1 – Audit & Information Gathering
1. **Inventory existing instructions.** ✅ (See `docs/react_editor_docs_audit.md`.)
   - Reviewed the root-level `Agents.md` and confirmed it lacks frontend-specific workflows.
   - Catalogued current `docs/` coverage, noting the absence of React/Vite guidance and component documentation.
   - Documented divergences between the frontend API client and the existing REST/schema references, including missing endpoints and version metadata in the published specs.
2. **Map the frontend code structure.**
   - Document the routing hierarchy defined in `web/scene-editor/src/App.tsx` and `routes/SceneEditorLayout.tsx`, noting placeholder views and shared layout primitives.
   - Summarize available component groups in `web/scene-editor/src/components/` (layout, navigation, display, forms, graph, scene-editor) including their intended usage and styling conventions.
   - Capture state management patterns exposed in `web/scene-editor/src/state/sceneEditorStore.ts` and API abstraction layers in `web/scene-editor/src/api/`.
3. **Trace integration seams.**
   - Describe how frontend placeholders are expected to connect with backend story data (`src/textadventure/` modules, FastAPI endpoints, persistence utilities).
   - Record assumptions the React editor makes about scene metadata, validation, and navigation logs so backend contributors understand required contracts.

## Phase 2 – Update Agent-Facing Guides
4. **Revise the root `Agents.md`.**
   - Add a "Frontend Workflow" section summarizing npm scripts, testing expectations (`npm run test`, `npm run typecheck`, linting commands), and screenshot guidance.
   - Clarify coordination rules when touching both Python and TypeScript code (e.g., run `pytest` + `mypy` alongside `npm` checks).
   - Reference the new frontend sub-guides created in later phases.
5. **Author scoped guidance for the web editor.**
   - Create `web/scene-editor/AGENTS.md` detailing code style (TypeScript strictness, React component conventions, Tailwind utility usage, accessibility requirements).
   - Document expectations for routing updates, state store changes, and API client modifications within the scope of the web editor.
   - Include instructions for updating associated story-driven docs whenever frontend data contracts evolve.
6. **Embed component-level instructions.**
   - For complex directories (`components/scene-editor`, `components/graph`), add nested `AGENTS.md` files capturing domain-specific rules (e.g., confirmation dialog accessibility, graph rendering patterns, performance considerations).
   - Link these scoped guides back to shared design tokens defined in `tailwind.config.js` and `src/index.css`.

## Phase 3 – Expand Formal Documentation
7. **Create a dedicated React editor overview.**
   - Write `docs/react_scene_editor_overview.md` that explains the product vision, page structure, navigation flow, and planned roadmap milestones hinted at in layout copy.
   - Include diagrams or tables summarizing the relationship between pages (`OverviewPage.tsx`, `SceneLibraryPage.tsx`, etc.) and backend services.
8. **Document component library usage.**
   - Add a `docs/frontend_component_catalog.md` describing each reusable component (props, state expectations, styling notes) with code snippets pulled from current implementations.
   - Highlight extension points for upcoming features (validation callouts, collaborative presence indicators) so future tasks understand intended growth paths.
9. **Update API and schema references.**
   - Cross-link `docs/web_editor_api_spec.md` and `docs/web_editor_schema.md` with the new React overview, ensuring all referenced endpoints and data structures reflect current backend modules.
   - Introduce changelog sections so contributors can track when payload shapes change and coordinate updates across frontend/backends.
10. **Enhance onboarding docs.**
    - Amend `docs/getting_started.md` and `docs/contributing.md` with a unified onboarding checklist that covers both Python CLI and web editor setup.
    - Provide troubleshooting tips tailored to the Vite dev server, Tailwind JIT compilation, and TypeScript type errors.

## Phase 4 – Create Maintenance Processes
11. **Establish documentation ownership.**
    - Define responsibility matrices (who updates AGENTS, who maintains API specs) and document them in `docs/best_practices.md`.
    - Encourage PR templates or checklists that include "Documentation reviewed/updated" items.
12. **Automate validation where possible.**
    - Add linting or CI checks that ensure scoped `AGENTS.md` files exist for key frontend directories.
    - Consider a docs spell-checker or link checker integrated into the existing CI pipeline.
13. **Schedule regular audits.**
    - Propose quarterly or milestone-based reviews of the React documentation stack, tying them to roadmap deliveries noted in the layout (e.g., validation overlays, collaborative features).
    - Track action items in `TASKS.md` or a future planning board to prevent documentation drift.

## Phase 5 – Knowledge Sharing & Examples
14. **Curate example-driven tutorials.**
    - Develop step-by-step guides showing how to add a new scene editing workflow, including backend schema updates and frontend UI wiring.
    - Publish these guides under `docs/tutorials/` (create directory if absent) and reference them from scoped AGENTS instructions.
15. **Capture design rationale.**
    - Expand `docs/architecture_overview.md` with a section summarizing why Vite + React + Tailwind were chosen, trade-offs considered, and how they complement the Python runtime.
    - Document any domain-specific terminology used in the UI (e.g., "navigation log", "validation overlays") with definitions to aid cross-team communication.
16. **Encourage example PR narratives.**
    - Provide a template in `docs/contributing.md` for documenting frontend-heavy PRs (screenshots, accessibility notes, state changes) and reference the screenshot policy found in the updated AGENTS guide.

## Phase 6 – Continuous Feedback Loop
17. **Gather contributor feedback.**
    - Set up a lightweight survey or issue label for documentation improvement requests and mention it in `Agents.md` and `docs/contributing.md`.
    - Encourage contributors to append quick notes in `logs/` or a shared changelog whenever they discover implicit assumptions not yet captured.
18. **Iterate on the plan.**
    - After initial updates land, reassess gaps using retro meetings or async check-ins, then append follow-up tasks to this `TASKS_DOCS.md` file or `TASKS.md` as needed.
    - Keep the plan evergreen by marking completed steps with dates or follow-up references.

Executing these phases will align the AGENTS instructions, formal documentation, and practical onboarding materials, giving future agents clear guidance for both the backend runtime and the evolving React scene editor.
