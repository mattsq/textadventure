# Troubleshooting Guide

This guide captures common issues encountered when running the text-adventure CLI or
experimenting with the agent framework. Each section lists symptoms, likely causes,
and recommended fixes so you can get back to exploring quickly. Skim the **General
Diagnostics** checklist first—most issues are resolved by double-checking the local
environment and running the automated quality gates. When a quick scan is not
enough, jump to the section that matches the observed symptoms.

## General Diagnostics

1. **Validate Python setup** – Confirm `python --version` reports 3.9 or newer and that
   you are running commands from the virtual environment created for this project.
   Activate it with `source .venv/bin/activate` (or `.venv\Scripts\activate` on Windows).
2. **Confirm dependencies** – Run `pip list` inside your virtual environment and ensure
   every package from `requirements.txt` is installed. Re-run
   `pip install -r requirements.txt` if anything is missing or outdated.
3. **Run the automated checks** – Execute `pytest -q`, `mypy src`, `ruff check src tests`,
   and `black --check src tests` to catch regressions introduced by local changes.
4. **Inspect logs** – When invoking the CLI, pass `--log-file path/to/transcript.jsonl`
   to capture narration, choices, and agent metadata for post-mortem analysis.
5. **Reset session data** – Delete the directory used with `--session-dir` (defaults to
   `.textadventure_sessions`) to remove stale snapshots before restarting an adventure.
6. **Compare against a clean repo** – If behaviour diverges significantly, run
   `git status` and inspect local modifications. Temporarily stashing large or
   experimental changes often isolates the regression quickly.

For a structured walkthrough of the setup process, see
[`docs/getting_started.md`](getting_started.md). The
[`docs/feature_reference.md`](feature_reference.md) file includes a section that
summarises the available CLI commands and flags mentioned throughout this guide.

## CLI Fails to Launch

- **Symptom:** Running `python src/main.py` raises `ModuleNotFoundError` errors.
  - **Cause:** The project dependencies were not installed in the active Python
    environment.
  - **Fix:** Activate your virtual environment and run `pip install -r requirements.txt`.

- **Symptom:** The CLI immediately exits with `OSError: [Errno 30] Read-only file system`.
  - **Cause:** The configured session directory or log file path is not writable.
  - **Fix:** Specify a writable location via `--session-dir` and/or `--log-file`, or run
    the CLI from a directory where you have write permissions.

- **Symptom:** `python src/main.py --help` reports unknown arguments that should exist.
  - **Cause:** You may be invoking a different copy of the repository or an old installation.
  - **Fix:** Confirm your working directory matches the cloned repository and rerun the command.

## Persistence Errors

- **Symptom:** Loading a saved session raises `InvalidSessionError` messages.
  - **Cause:** The snapshot file is malformed or was created by an incompatible version.
  - **Fix:** Verify the session ID in `--session-dir` matches an existing save. If the
    schema changed, start a new game or restore from a compatible backup.

- **Symptom:** Progress appears to reset after restarting the CLI.
  - **Cause:** Persistence is disabled by default.
  - **Fix:** Launch the CLI with `--session-dir .textadventure_sessions --session-id demo`
    (or any preferred identifier) before issuing commands you want to resume later.

## Tool and Knowledge Base Issues

- **Symptom:** Invoking a scripted tool (for example, `lookup lore`) does nothing.
  - **Cause:** The scripted engine only exposes tools that were registered for the
    current scene or coordinator configuration.
  - **Fix:** Check the scene definition to ensure the tool command is present. When
    running custom adventures, verify `ScriptedStoryEngine` received the expected
    tool registry during initialisation.

- **Symptom:** Knowledge base responses repeat stale information.
  - **Cause:** Session persistence restores the last cached tool results.
  - **Fix:** Delete the relevant snapshot under the session directory or run the CLI
    with a new `--session-id` to start from a clean slate. You can also disable
    persistence temporarily to confirm the stale data is tied to the snapshot.

- **Symptom:** Custom tools crash with `TypeError` or missing-argument errors.
  - **Cause:** Tool implementations must conform to the `Tool` protocol and accept the
    expected payload shape.
  - **Fix:** Revisit `textadventure/tools.py` and update the custom tool signature to
    match the interface. Add unit tests that exercise the tool via the coordinator to
    catch mismatches earlier.

## LLM Integration Issues

- **Symptom:** The CLI reports `Unknown provider` when using `--llm-provider`.
  - **Cause:** The provider identifier is misspelled or the adapter is not registered.
  - **Fix:** Run `python src/main.py --list-llm-providers` to view available adapters.
    For custom adapters, double-check the `module:factory` import path.

- **Symptom:** LLM requests fail with authentication errors.
  - **Cause:** Missing or invalid API credentials passed through `--llm-option` flags.
  - **Fix:** Re-enter the API key or token. When using environment variables, confirm
    they are exported in the shell running the CLI.

- **Symptom:** The CLI times out when contacting a local Text Generation Inference (TGI)
  server.
  - **Cause:** The TGI process is not running, or the `--llm-option base_url=` value is incorrect.
  - **Fix:** Start the TGI server, ensure it binds to the expected host/port, and update
    the `base_url` option accordingly.

## Multi-Agent Coordination Problems

- **Symptom:** Secondary narration never appears even though an LLM provider is configured.
  - **Cause:** The agent may be filtering outputs due to validation failures or low
    confidence.
  - **Fix:** Enable debug logging with `--log-file` and inspect the transcript for
    suppressed events. Adjust prompt configuration or review validation errors emitted
    by `LLMStoryAgent`.

- **Symptom:** The CLI exits with `CoordinatorError` mentioning pending messages.
  - **Cause:** A tool or agent enqueued messages without recipients.
  - **Fix:** Verify custom tools declare valid `target_agent` values and that scripted
    scenes reference known agent identifiers.

## Analytics & Reporting

- **Symptom:** `python src/main.py analytics` fails with validation errors on a custom scene file.
  - **Cause:** The adventure data includes duplicate commands or missing transitions.
  - **Fix:** Run `textadventure.validate_scenes` from a Python REPL (see
    `docs/data_driven_scenes.md`) to pinpoint the problematic entries.

- **Symptom:** Analytics reports show zero reachable scenes.
  - **Cause:** The starting scene identifier in the data does not match any scene key.
  - **Fix:** Update the `start_scene` field or rename the scene identifier to match the
    configured entry point.

## Getting Additional Help

If an issue is not covered above:

- Search the repository issues or documentation for similar reports.
- Capture a minimal reproduction script or transcript demonstrating the problem.
- Share environment details (`python --version`, operating system, installed provider versions).

Contributions that expand this guide with new scenarios are welcome—open a pull request with the
symptom, diagnosis steps, and verified resolution.
