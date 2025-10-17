# Tutorial: Playtesting & Publishing Workflow

This guide completes the scene editor tutorial series by showing how to validate your branching story, capture actionable feedback, and prepare export artifacts for sharing or deployment. Follow these steps after wiring conditional logic in **Part 3 – Branching Narrative Authoring** so your adventure ships with confidence.

## Prerequisites

- Completed the earlier tutorials (Parts 1–3) and have a playable project with at least one branching beat.
- The Vite development server is running (`npm run dev` from `web/scene-editor`).
- You are comfortable navigating the editor panels described in the [Scene Editor Overview](../react_scene_editor_overview.md).

## 1. Launch the Playtest Console

1. From any project page, click **Launch Playtest** in the global header toolbar.
2. The playtest console opens in a split-pane layout with a transcript timeline on the left and context details on the right.
3. Verify the starting narration matches the scene configured as your project's starting location.
4. Use the **Reset session** control if you need to restart the simulation from a clean world state.

> 📸 *Screenshot reminder:* Capture a desktop-resolution screenshot of the playtest console with annotations enabled. Save it as `docs/tutorials/images/part4-playtest-console.png` for future documentation updates.

## 2. Exercise Branches and Record Transcripts

1. Play through each branch introduced in Part 3. Use the on-screen choice buttons to trigger conditional outcomes.
2. When a state mutation occurs, confirm it appears in the **State changes** inspector. Hover over entries to review metadata such as timestamps and triggering scenes.
3. Click **Add transcript note** to jot down observations or bug reproduction steps. Notes are timestamped and persist with the session export.
4. Download the transcript log using **Export transcript (.json)** after each exploratory run. Store files alongside QA artifacts for traceability.

## 3. Log Bugs and Follow-Up Tasks

1. Switch to the **Annotations** tab in the right rail to review collaborative comments left by teammates.
2. Use **New annotation** to flag narrative issues, pacing concerns, or missing assets. Assign owners and set severity levels so the backlog stays actionable.
3. Cross-reference annotations with transcript notes to ensure every reported issue has reproduction steps.
4. Resolve annotations directly from the panel once fixes land. The history view tracks status changes for audit purposes.

## 4. Run Validation & Analytics Checks

1. Open the **Validation** panel below the playtest transcript to surface automated warnings and blockers.
2. Address any **Blocking** items first (e.g., unreachable scenes or missing choice destinations). Links in each row navigate to the relevant editor forms.
3. Review **Advisory** notices for polish opportunities such as long prompts or unlocalized strings.
4. Generate the analytics summary via **Download analytics report (.json)** to capture reachability metrics and content distribution snapshots that accompany your release notes.

## 5. Export the Adventure Package

1. Return to the project dashboard and click **Export → Scene Package**.
2. Choose a destination folder for the generated archive (`.zip` format). The bundle contains scene data, metadata manifests, and asset references.
3. Enable **Include transcripts** if you want the most recent playtest logs packaged with the export for reviewers.
4. After export completes, open the manifest preview dialog to verify version numbers, build timestamps, and checksum details.

## 6. Publish and Share with Stakeholders

1. Upload the exported archive to your chosen distribution channel (e.g., shared drive, internal marketplace draft, or automated CI pipeline).
2. In parallel, update the CLI adventure repository if you are maintaining a scripted counterpart. Use the `textadventure` CLI `--scene-file` flag to confirm the exported data plays as expected.
3. Post a summary in your team's communication channel that links to:
   - The exported archive location.
   - Analytics and transcript reports.
   - Outstanding annotations or TODOs that need follow-up before release.
4. Track reviewer feedback and close annotations as they are addressed. Re-run targeted playtests after fixes to maintain confidence.

## 7. Wrap Up & Next Steps

- Update `TASKS_DOCS.md` to mark Part 4 of the tutorial series as complete and note any remaining follow-ups (such as capturing fresh screenshots).
- Encourage collaborators to review the entire tutorial sequence so onboarding stays consistent.
- Continue iterating on documentation by drafting frontend PR narrative templates and establishing the documentation feedback channel outlined in `TASKS_DOCS.md` Phase 6.
