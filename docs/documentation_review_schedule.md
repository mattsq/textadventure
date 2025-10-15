# Documentation Review Schedule

This schedule formalises recurring audits so the documentation set remains accurate as the text adventure framework evolves.

## Cadence Overview

| Review Window | Scope | Primary Steward | Activities |
| --- | --- | --- | --- |
| Quarterly (Jan/Apr/Jul/Oct) | Core contributor docs (`docs/getting_started.md`, `docs/contributing.md`, root `Agents.md`) | Docs steward on rotation | Verify setup instructions, tooling expectations, and PR checklist language; ensure new automation steps are documented. |
| Biannual (Mar/Sep) | Frontend-specific guides (`docs/react_scene_editor_overview.md`, `docs/frontend_component_catalog.md`, `web/scene-editor/AGENTS.md` hierarchy) | Frontend lead | Confirm component catalog accuracy, update screenshots policy, and align scoped `AGENTS.md` with current architecture. |
| Annual (Nov) | Deep reference materials (`docs/web_editor_schema.md`, `docs/web_editor_api_spec.md`, analytics/architecture notes) | Backend representative + docs steward | Cross-check schema changes, regenerate diagrams, and log any deprecations or migration paths. |

## Audit Workflow

1. **Kickoff:** Open a dated tracking issue (or add to `TASKS.md`) two weeks before the review window begins. Assign the steward(s) and outline focus areas.
2. **Inventory & Flag:** During the window, skim the targeted documents and list gaps, outdated screenshots, or missing automation references in the tracking issue.
3. **Update & Verify:** Land documentation patches and ensure CI guardrails (once implemented) pass with the refreshed content.
4. **Record Outcomes:** Append a short summary to the tracking issue with links to merged PRs and remaining follow-ups. Close the issue or move residual work to `TASKS.md`.

## Templates

- **Tracking Issue Title:** `Docs review – <Scope> – <Month YYYY>`
- **Checklist Starter:**
  - [ ] Audit completed documents listed in the scope
  - [ ] Outstanding action items transferred to `TASKS.md`
  - [ ] Feedback channel updated with latest review date

Maintaining this schedule ensures the broader documentation plan in `TASKS_DOCS.md` stays actionable and that contributors can rely on up-to-date guidance.
