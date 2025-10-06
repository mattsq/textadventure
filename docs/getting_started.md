# Getting Started with the Text Adventure Agent Playground

This guide walks through installing the project, launching the bundled demo adventure, and exploring the more advanced agent-driven features that ship with the repository. Follow these steps if you are new to the codebase or want a refresher on the available tooling.

## 1. Prerequisites

- **Python**: Version 3.9 or newer is required.
- **Operating system**: The project is routinely tested on macOS, Linux, and Windows. All commands shown below work in a POSIX shell; Windows users can run them from PowerShell with minor adjustments noted inline.
- **Optional dependencies**: Some features (such as LLM provider integrations) require third-party SDKs. These are declared in `requirements.txt` and can be installed as needed.

## 2. Clone the Repository

```bash
git clone https://github.com/your-org/textadventure.git
cd textadventure
```

If you are working from a fork, replace the repository URL with the fork address.

## 3. Create a Virtual Environment

Isolating dependencies in a virtual environment keeps your global Python installation clean and ensures reproducible runs.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

Once activated, your shell prompt will include the virtual environment name. Deactivate it at any time with `deactivate`.

## 4. Install Dependencies

Install the runtime and development dependencies:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

The requirements file tracks the packages used by the CLI demo, the LLM provider adapters, and the automated test suite. If you only need the CLI experience you can skip optional extras like provider SDKs by installing the specific subset you require.

## 5. Run the Demo Adventure

Launch the scripted text adventure from the repository root:

```bash
python src/main.py
```

The CLI will print the current scene narration, available choices, and a prompt for your next command. Enter `help` to see built-in commands such as `save`, `load`, `status`, `editor`, and `quit`, or type `tutorial` for an interactive walkthrough of the same features.

### Enable Persistence and Logging

Pass additional flags to capture session data or attach log files:

```bash
python src/main.py \
  --session-dir sessions \
  --session-id demo \
  --log-file transcripts/demo.log
```

- `--session-dir` sets the directory where save files are stored (it will be created if it does not exist).
- `--session-id` controls the save-file prefix so multiple runs can coexist.
- `--log-file` writes a structured transcript containing narration, player input, and agent metadata.

### Improve CLI Readability

Switch to a brighter colour palette when running the CLI in low-light or
low-vision environments:

```bash
python src/main.py --high-contrast
```

The `--high-contrast` flag tweaks heading colours, list bullets, and inline
formatting so narration and choices stand out more clearly on terminals with
reduced contrast or accessibility themes.

### Launch the Scene Editor API

Type `editor` inside the CLI to start the FastAPI application that powers the web-based scene editor. The command reports the local URL and supports `editor stop`/`editor status` for lifecycle control. Configure the binding with the following command-line flags when starting the CLI:

```bash
python src/main.py --editor-host 0.0.0.0 --editor-port 9000
```

- `--editor-host` selects the network interface exposed by the editor API (defaults to `127.0.0.1`).
- `--editor-port` chooses the listening port (defaults to `8000`).
- `--no-editor` disables the `editor` command entirely for environments where launching subprocesses is undesirable.

When you want to iterate on the scripted scenes alongside the editor, start the
CLI with `--scene-path path/to/scenes.json` (or set
`TEXTADVENTURE_SCENE_PATH`). The adventure will load data from that file and
watch it for changes between turns, so edits in the web UI or another editor
appear immediately without restarting the session.

### Add an LLM Co-narrator

To experiment with hybrid scripted + LLM storytelling, register an LLM provider via the registry flags:

```bash
python src/main.py \
  --llm-provider openai \
  --llm-option api_key="sk-demo" \
  --llm-option model="gpt-4o-mini"
```

You can supply repeated `--llm-option key=value` pairs to configure the selected provider. Values are parsed as JSON when possible, so booleans and numbers do not need to be quoted. Alternatively, store the configuration in a JSON file and load it with `--llm-config path/to/config.json`.

## 6. Run Quality Gates

Before contributing code changes, run the same checks enforced by the continuous integration pipeline:

```bash
pytest -q
mypy src
ruff check src tests
black --check src tests
```

Running these commands locally ensures unit tests, type checks, linting, and formatting all pass before you open a pull request.

## 7. Explore Advanced Tools

- Review `docs/data_driven_scenes.md` to author new adventures using the JSON scene format.
- Consult `docs/llm_capabilities.md` for details on the provider capability schema and how to register new adapters.
- Read `docs/best_practices.md` for narrative design guidance and analytics tips.
- Dive into `docs/multi_agent_orchestration.md` to understand how multi-agent storytelling works inside the coordinator.

## 8. Troubleshooting

If you encounter issues:

- Verify your virtual environment is active and the dependencies installed successfully.
- Re-run the quality gates to surface stack traces or type-checking errors.
- Check `docs/troubleshooting.md` for solutions to common problems with provider configuration, persistence, or the CLI.
- Search the issue tracker (or open a new issue) with details about your environment and steps to reproduce the problem.

## 9. Next Steps

Once you are comfortable with the demo, experiment with:

- Extending `scripted_scenes.json` or loading your own scene files via `ScriptedStoryEngine`.
- Registering additional agents through `MultiAgentCoordinator` to prototype new narrative behaviours.
- Writing automated tests in `tests/` to cover your custom logic.
- Contributing documentation to share learnings with the community.

Happy adventuring!
