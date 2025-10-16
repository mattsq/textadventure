# Tutorial: Author Your First Branching Scene

This guide walks through the third installment of the scene editor tutorial series. You will build a short branching story that reacts to player choices and state flags, preview the flow in the graph inspector, and prepare for playtesting.

## Prerequisites

- Completed the setup steps in **Part 1 – Environment Setup & First Launch**.
- Created the base project skeleton from **Part 2 – Scene Fundamentals** with two connected locations.
- Familiarity with the terminology in the [Scene Editor Overview](../react_scene_editor_overview.md) and the component catalog entries for forms and graph widgets.

## 1. Plan the Branching Beat

Before opening the editor, outline the narrative beat you want to author:

- **Context:** The player arrives at the `Atrium` location and meets an archivist NPC.
- **Choice:** Offer help, ask for archives access, or leave immediately.
- **Outcomes:** Helping grants a `research_pass` flag; asking politely yields a delayed reward; leaving forwards the player to the courtyard without rewards.

Document the outcomes in your design doc or the editor's notes field so reviewers can trace intent to implementation.

## 2. Create Choice Prompt and Options

1. Open the project and navigate to the `Atrium` scene.
2. In the **Choice Blocks** section, click **Add Branching Choice**.
3. Fill out the base prompt:
   - **Prompt title:** `Archivist Introduction`
   - **Display text:** Provide a short narrative that sets up the archivist encounter.
   - **Player choices:** Add three options labeled "Offer help", "Request access", and "Leave quietly".
4. For each option, set a concise summary that will appear in transcript exports.

> 💡 *Accessibility tip:* Keep option labels under 60 characters to prevent wrapping issues in smaller viewports.

## 3. Wire Conditional Outcomes

For each choice option, configure outcomes in the **Result & Conditions** panel.

### Offer Help

- **Condition:** None (available by default).
- **State updates:** Add a state mutation that sets `research_pass = true`.
- **Next scene:** Remain in `Atrium` but enqueue a follow-up dialogue beat by enabling **Trigger follow-up event** and selecting `Archivist Gratitude`.
- **Notes:** Mention that this unlocks additional archival content in later tutorials.

### Request Access

- **Condition:** Add a check that `research_pass` is not already granted to avoid duplication.
- **State updates:** None.
- **Next scene:** Route to a new scene `Archives Lobby` that you will author in Part 4.
- **Notes:** Include reviewer notes about needing an approval flag before the route is usable in playtests.

### Leave Quietly

- **Condition:** None.
- **State updates:** Clear any queued follow-up events to avoid dangling conversations.
- **Next scene:** Set to `Courtyard`.
- **Notes:** Explain that this branch is effectively a player opt-out path.

## 4. Preview in the Graph Inspector

Open the **Graph** tab to verify the branching logic:

1. Ensure the three outgoing edges from `Atrium` are visible.
2. Hover over each edge to confirm the condition badges (`Always`, `When research_pass is false`, `Always`).
3. Drag the new `Archives Lobby` placeholder node into view so reviewers can trace the planned continuation.

![Branching choice editor annotated](images/part3-branching-choice.png)

If an edge is missing, return to the form and confirm each choice has a destination scene selected.

## 5. Document Playtest Expectations

Add reviewer notes in the **Testing Expectations** sidebar:

- Describe how to reach each branch during playtesting (e.g., "Choose Offer help after the initial exploration beat").
- Note the state mutations to watch (`research_pass` toggling).
- Link to any manual QA scripts or user feedback templates stored elsewhere in the repository.

## 6. Next Steps

You now have a branching narrative beat with stateful outcomes. Continue to **Part 4 – Playtesting & Publishing** to verify the logic in the playtest console, capture feedback, and prepare release artifacts.

Update the `TASKS_DOCS.md` tracker once your branch lands so the team can record tutorial progress.
