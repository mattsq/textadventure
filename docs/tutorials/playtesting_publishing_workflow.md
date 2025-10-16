# Tutorial: Playtesting & Publishing Workflow

This guide serves as the fourth installment of the scene editor tutorial series. You will validate your branching content in the built-in playtest console, collect actionable feedback, and prepare export artifacts for reviewers or downstream toolchains.

## Prerequisites

- Completed the first three tutorials in this series (environment setup, scene fundamentals, and branching narrative authoring).
- A project that includes the branching beat from Part 3, including the `research_pass` state flag and `Archives Lobby` placeholder scene.
- Access to the [Scene Editor Overview](../react_scene_editor_overview.md) and [Frontend Component Catalog](../frontend_component_catalog.md) for terminology reference.
- Optional: Shared storage location (e.g., versioned `playtest-notes/` directory) for uploading exported builds and transcripts.

## 1. Launch the Playtest Console

1. From the scene editor header toolbar, click **Launch Playtest**. The console opens in a split-pane layout beside the canvas.
2. Confirm the console sidebar shows the current project name, build timestamp, and validation summary.
3. Use the **Reset State** button to ensure the session starts from the configured starting location (`atrium`).

> 🎯 *Goal:* Begin every playtest session from a known state so bugs reproduce consistently across contributors.

## 2. Walk Through Each Branch

1. Play through the tutorial scenario until you reach the `Archivist Introduction` branching choice created in Part 3.
2. Exercise each option sequentially:
   - **Offer help:** Verify the narration acknowledges the archivist and that `research_pass` is granted in the session state inspector.
   - **Request access:** Confirm the console routes to the `Archives Lobby` placeholder and logs a note about pending content.
   - **Leave quietly:** Ensure the player transitions to the `Courtyard` scene without receiving the `research_pass` flag.
3. After each branch, use **Reset State** to return to the starting location before exploring the next option.

## 3. Capture Transcript Snippets

1. Expand the **Transcript** tab in the playtest console.
2. Copy the log entries covering the branching choice and outcomes. Use the **Copy to Clipboard** button to preserve formatting.
3. Paste the snippets into your shared notes document or issue tracker entry, highlighting any unexpected text or pacing issues.
4. If localization is planned, flag dialogue that needs translation review.

## 4. Log Bugs and Feedback Inline

1. Open the **Playtest Notes** sidebar (speech-bubble icon) adjacent to the console.
2. For each issue discovered, create an entry with:
   - **Title:** Concise summary (e.g., `Archivist gratitude line repeats`).
   - **Severity:** Choose `Bug`, `Polish`, or `Observation` using the dropdown.
   - **Reproduction steps:** Reference the transcript snippet or state flag transitions.
   - **Follow-up owner:** Assign a teammate or leave unassigned for triage.
3. Export the notes as Markdown (`Export → Markdown`) and commit them to `playtest-notes/` or attach them to the relevant GitHub issue.

## 5. Annotate the Playtest Screenshot

Reviewers expect a screenshot demonstrating the console layout and annotations:

1. Resize the browser to a desktop viewport (minimum 1280px wide).
2. Ensure the branching choice transcript, session state inspector, and notes sidebar are visible simultaneously.
3. Toggle **Overlay annotations** in the console toolbar to highlight state mutations.
4. Capture the screenshot and save it as `docs/tutorials/images/part4-playtest-console.png`.
5. Reference the image in future documentation or PRs when describing the playtest workflow.

## 6. Export the Scene Package

1. From the header toolbar, click **Export → Scene Package (JSON)**.
2. Choose an export directory within your repository clone (for example, `exports/tutorial-part4/`).
3. Enable the **Include validation report** checkbox to bundle schema warnings.
4. Click **Export** and wait for the completion toast.

## 7. Review Validation Output

1. Navigate to the export directory and open the generated `validation_report.json`.
2. Confirm the report lists zero errors. Warnings about placeholder scenes (`Archives Lobby`) are acceptable at this stage—note them for follow-up.
3. If errors surface, return to the editor to resolve broken references, missing dialogue, or schema mismatches.

## 8. Share Playtest Builds with Reviewers

1. Compress the exported package and validation report into a zip archive (e.g., `tutorial-part4-playtest.zip`).
2. Upload the archive and Markdown notes to your shared storage location or attach them to a GitHub issue/PR.
3. In the PR description, summarize:
   - Which branches you exercised.
   - Outstanding warnings that reviewers should ignore or investigate.
   - Links to the transcript snippets and playtest notes.

## 9. Wrap Up and Next Steps

- Update `TASKS_DOCS.md` to mark **Part 4 – Playtesting & Publishing** as complete once this documentation merges.
- Plan a follow-up iteration to replace the `Archives Lobby` placeholder with fully scripted content.
- Continue the feedback loop by reviewing the automation recommendations in `docs/documentation_automation_recommendations.md` and proposing enhancements as needed.
