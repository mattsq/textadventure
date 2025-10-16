# Tutorial: Environment Setup & First Launch

This guide covers the first installment of the scene editor tutorial series. By the end, you will have the Python and Node.js dependencies installed, the React scene editor running locally, and a high-level tour of the interface captured for reviewers.

## Prerequisites

- macOS, Linux, or Windows workstation with terminal access.
- Basic familiarity with the repository layout described in the [Scene Editor Overview](../react_scene_editor_overview.md).
- Optional: GitHub account with access to the project repository if you plan to push changes.

## 1. Verify Toolchain Versions

Before installing dependencies, confirm the required runtimes are available:

```bash
node --version
npm --version
python3 --version
```

Ensure Node.js 18+, npm 9+, and Python 3.9+ are installed. If any command fails or reports an older version, follow the platform-specific installation steps in the [Getting Started guide](../getting_started.md).

## 2. Bootstrap the Python Environment

1. Navigate to the repository root in your terminal.
2. Create and activate a virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
   ```

3. Install backend dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Run the scripted smoke test to confirm the CLI entry point works:

   ```bash
   python src/main.py --help
   ```

   You should see usage information for the text adventure runtime, including flags for session persistence and logging.

## 3. Install Frontend Dependencies

1. Change into the scene editor workspace:

   ```bash
   cd web/scene-editor
   ```

2. Install Node dependencies:

   ```bash
   npm install
   ```

3. (Optional) Run the TypeScript checker to confirm the local toolchain is healthy:

   ```bash
   npm run typecheck
   ```

   Resolve any missing package or type definition errors before proceeding.

## 4. Launch the Development Server

1. From `web/scene-editor`, start the Vite dev server:

   ```bash
   npm run dev
   ```

2. The terminal prints the local URL (typically `http://localhost:5173/`). Open it in your browser.
3. Verify that hot module replacement works by saving a small change in `web/scene-editor/src/App.tsx` and confirming the page refreshes automatically.
4. Keep the dev server running for the interface tour in the next section.

## 5. Tour the Workspace Chrome

Use the running instance to familiarize yourself with the key interface regions:

- **Global navigation:** The sidebar hosts project selection, scene lists, and search tools. Expand each section to observe how the layout responds.
- **Canvas area:** Displays dashboards, form editors, or graph visualizations depending on the selected module.
- **Inspector panels:** Contextual settings, validation warnings, and collaboration activity feed appear along the right rail.
- **Dev server indicator:** The footer includes a status pill showing connection health and build warnings.

As you explore, make quick notes about terminology differences or questions to follow up on with the team. These insights inform later tutorial installments.

## 6. Capture the Dashboard Screenshot

Reviewers expect a screenshot of the landing dashboard with the dev server indicator visible:

1. Resize the browser to a desktop viewport (minimum 1280px wide).
2. From the dashboard view, confirm the status pill reads **Connected**.
3. Use your operating system screenshot tool to capture the full workspace chrome.
4. Save the image as `docs/tutorials/images/part1-dashboard.png` and reference it in documentation updates or PR descriptions.

## 7. Wrap Up and Next Steps

- Stop the dev server with `Ctrl+C` in the terminal.
- Deactivate the Python virtual environment (`deactivate`) if you are pausing work.
- Record any setup hiccups or environment notes in the project issue tracker.
- Continue to **Part 2 – Scene Fundamentals** to begin authoring locations and navigation paths.

Update `TASKS_DOCS.md` to reflect completion of the Part 1 tutorial documentation once your changes merge.
