# Tutorial: Scene Fundamentals & Navigation Wiring

This guide covers the second installment of the scene editor tutorial series. You will set up core project metadata, author two connected locations, and verify navigation flows in the graph view. By the end, reviewers should see a playable skeleton ready for branching logic.

## Prerequisites

- Completed **Part 1 – Environment Setup & First Launch** and have the dev server running locally.
- Familiarity with layout terminology from the [Scene Editor Overview](../react_scene_editor_overview.md) and relevant form component entries in the [Frontend Component Catalog](../frontend_component_catalog.md).
- A high-level story concept you want to translate into scenes (even a simple two-room prototype).

## 1. Create a New Project Shell

1. In the global navigation sidebar, click **Projects → New Project**.
2. Provide a working title such as `Museum Heist Tutorial` and optional description for future collaborators.
3. Accept the default storage path or specify a dedicated workspace folder.
4. Click **Create Project**. The editor redirects to the empty scene dashboard with summary tiles for locations, actions, and validation alerts.

> 📌 *Tip:* Keep tutorial projects separate from production workspaces so exported JSON packages stay organized.

## 2. Configure Project Metadata

1. From the dashboard, open the **Project Settings** panel in the right inspector rail.
2. Populate the following fields:
   - **Tagline:** Short summary (e.g., `Infiltrate the after-hours museum gala`).
   - **Default player state:** Add a description for starting inventory or flags (e.g., `{ "has_badge": false }`).
   - **Starting location:** Leave blank until the first location is created; you will return to set this later.
3. Click **Save Settings** to persist the metadata. Resolve any validation warnings surfaced below the form.

## 3. Add the First Location

1. Navigate to **Locations → Add Location**.
2. Fill out the base fields:
   - **Location ID:** `atrium`
   - **Display name:** `Museum Atrium`
   - **Description:** Write a paragraph setting the scene and introducing interactable elements.
3. In the **Entry Actions** section, add a welcome narration snippet or note reminding players about the gala objective.
4. Click **Save Location**. The sidebar updates with the new entry and a green checkmark indicating no validation errors.

## 4. Add a Connected Location

1. Still within **Locations**, select **Add Location** again.
2. Configure the second node:
   - **Location ID:** `security_wing`
   - **Display name:** `Security Wing`
   - **Description:** Briefly describe the surveillance hub and guards on patrol.
3. In the **Metadata** panel, flag the room as restricted if your story uses access checks later.
4. Save the location. Both entries now appear under the Locations list.

## 5. Wire Navigation Actions

1. Switch to the **Actions** module in the sidebar and choose **Add Navigation Action**.
2. Create a movement option from the atrium to the security wing:
   - **Action ID:** `atrium_to_security`
   - **Source location:** `atrium`
   - **Target location:** `security_wing`
   - **Prompt text:** "Slip through the maintenance door toward the security wing."
3. Under **Requirements**, leave the fields empty for now so the action is always available.
4. Save the action, then repeat the process for the return trip using:
   - **Action ID:** `security_to_atrium`
   - **Source location:** `security_wing`
   - **Target location:** `atrium`
   - **Prompt text:** "Head back to the bustling atrium."

## 6. Set the Starting Location and Test Draft Navigation

1. Open **Project Settings** again and set **Starting location** to `atrium`.
2. Click **Launch Playtest** in the header toolbar. The playtest console opens in a new panel.
3. Verify the initial narration references the atrium description.
4. Choose the navigation option to move into the security wing, then use the return action to confirm round-trip travel works.
5. Record any copy tweaks or future state gating ideas in the playtest notes sidebar.

## 7. Inspect the Graph View

1. Navigate to **Graph → Location Graph** from the sidebar.
2. Confirm both nodes (`Museum Atrium`, `Security Wing`) appear with a bidirectional edge.
3. Use the toolbar controls to enable label overlays and highlight navigation actions.
4. If layout adjustments are needed, drag nodes into a logical spatial arrangement before saving the graph state.

## 8. Capture the Screenshot Requirement

Reviewers expect visual confirmation of the connected locations:

1. With the graph still open, ensure both nodes and their connecting edge are visible without overlapping labels.
2. Switch the graph theme to light or dark mode to match the rest of the series for consistency.
3. Capture a screenshot at desktop resolution and save it as `docs/tutorials/images/part2-location-graph.png`.
4. Reference the screenshot in pull requests or future doc updates where the graph is discussed.

## 9. Wrap Up and Next Steps

- Add quick TODOs in your project issue tracker for future NPCs, puzzles, or gating logic inspired during playtesting.
- Update `TASKS_DOCS.md` when this tutorial documentation is merged to mark **Part 2** as complete.
- Continue to **Part 3 – Branching Narrative Authoring** to layer conditional choices onto this navigation skeleton.
