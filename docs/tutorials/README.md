# Scene Editor Tutorial Series

This directory collects step-by-step walkthroughs for the React-based scene editor. The goal is to give new contributors and content designers an approachable path from first launch to shipping review-ready scenes.

## Series Outline and Screenshot Requirements

The tutorial series is structured as four installments that build upon each other. Each part notes the core learning objectives and the screenshots reviewers expect when the guide is updated.

1. **Part 1 – Environment Setup & First Launch**
   - Focus: Install dependencies, run the local development server, and tour the workspace chrome.
   - Key checkpoints:
     - Verify Node.js, npm, and Python prerequisites.
     - Start the Vite dev server and confirm hot reload.
     - Capture a screenshot of the landing dashboard with the dev server status indicator visible.
   - Reference tutorial: [`environment_setup_first_launch.md`](environment_setup_first_launch.md)
2. **Part 2 – Scene Fundamentals**
   - Focus: Create a new project, define locations, and wire basic actions.
   - Key checkpoints:
     - Configure project metadata and default player state.
     - Add two locations and connect them with navigation actions.
     - Capture a screenshot of the location graph showing the new nodes and edges.
   - Reference tutorial: [`scene_fundamentals_navigation.md`](scene_fundamentals_navigation.md)
3. **Part 3 – Branching Narrative Authoring**
   - Focus: Layer conditional logic, branching choices, and outcome summaries.
   - Key checkpoints:
     - Add choice prompts and conditional transitions in the scene editor form.
     - Preview branching paths in the graph inspector.
     - Capture a screenshot of the branching choice editor with condition badges visible.
   - Reference tutorial: [`branching_scene.md`](branching_scene.md)
4. **Part 4 – Playtesting & Publishing**
   - Focus: Run the built-in playtest mode, collect feedback, and prepare export artifacts.
   - Key checkpoints:
     - Launch playtest, record transcript snippets, and note bug logging workflow.
     - Export the scene package and review JSON validation messages.
     - Capture a screenshot of the playtest console with annotations enabled.
   - Reference tutorial: [`playtesting_publishing_workflow.md`](playtesting_publishing_workflow.md)

> **Screenshot storage:** Place tutorial screenshots under `docs/tutorials/images/` with semantic filenames (e.g., `part3-branching-choice.png`). Update captions inline where the image is referenced.

## Review Checklist for Tutorial Updates

Use this checklist when authoring or reviewing changes in `docs/tutorials/`:

- [ ] Confirm the affected tutorial still aligns with the series outline (objectives, prerequisites, and hand-offs between parts).
- [ ] Verify command snippets are accurate for the current toolchain versions (Node.js, npm, Python, and repository scripts).
- [ ] Ensure every referenced UI element or workflow step has an accompanying screenshot or explicit rationale if visual updates are pending.
- [ ] Check that screenshot filenames follow the `partX-description.png` convention and live in `docs/tutorials/images/`.
- [ ] Run spell check (`codespell`) and link check (`lychee`) across the modified docs before approval.
- [ ] Update `TASKS_DOCS.md` with any newly completed milestones or follow-up actions discovered during review.
