# Agents Guide

## Repository Purpose

This project prototypes a small framework for running text adventures that are
orchestrated by autonomous agents. The codebase ships with a scripted demo
experience plus the building blocks for experimenting with multi-agent
coordination, tool use, LLM-backed storytellers, and session persistence.

## Key Components

The runtime code lives in `src/` and is published as the `textadventure`
package. Highlights include:

- **`src/main.py`** – CLI entry point that wires the world state, story engine,
  multi-agent coordinator, transcript logging, and optional persistence. It also
  exposes flags for registering LLM co-narrators through the provider registry.
- **`textadventure/world_state.py`** – data model describing locations, actors,
  inventory, observations, and remembered player actions.
- **`textadventure/memory.py`** – rolling log of agent memories plus utilities
  for replaying observations/actions.
- **`textadventure/story_engine.py`** – protocol defining how narrative beats
  are generated and formatted.
- **`textadventure/scripted_story_engine.py`** – deterministic story engine used
  by the demo adventure, including helpers for loading JSON scenes from disk or
  in-memory mappings.
- **`textadventure/multi_agent.py`** – lightweight coordinator that lets
  multiple agents take turns responding to player input while exposing debug
  metadata.
- **`textadventure/llm_story_agent.py`** – adapter that routes coordinator
  prompts through an LLM-backed decision-maker.
- **`textadventure/llm.py`** – abstractions for integrating LLM providers when
  experimenting with generative story engines (shared message/response models
  plus streaming helpers).
- **`textadventure/llm_provider_registry.py`** – command-line friendly registry
  that resolves provider identifiers, parses `--llm-option` flags, and builds
  configured clients.
- **`textadventure/llm_providers/`** – adapters for specific hosted and local
  LLM providers (OpenAI, Anthropic, Cohere, Hugging Face Text Generation
  Inference, and llama.cpp).
- **`textadventure/tools.py`** – base interfaces for tool-calling agents and a
  simple knowledge-base lookup tool.
- **`textadventure/persistence.py`** – session snapshot helpers and storage
  backends used by the CLI save/load commands.
- **`textadventure/data/scripted_scenes.json`** – bundled demo adventure
  definition consumed by the scripted engine.

Design notes and experiment write-ups live in `docs/`, and the automated test
suite resides under `tests/`.

## Environment Setup

1. Install Python 3.9 or newer.
2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Run the demo CLI:
   ```bash
   python src/main.py
   ```
   Use `python src/main.py --help` for persistence-related options like
   `--session-dir`, `--session-id`, and the `--log-file` transcript flag.

## Frontend Workflow Expectations

The scene editor lives under `web/scene-editor/` and relies on the Vite + React
toolchain with Tailwind CSS for styling. Contributors working on the frontend
must:

1. Install Node.js 18+ (to match the CI environment) and project dependencies:
   ```bash
   cd web/scene-editor
   npm install
   ```
2. Use the provided npm scripts during development and validation:
   - `npm run dev` – Launch the Vite dev server for local iteration.
   - `npm run build` – Produce a production build (run before committing
     significant UI changes).
   - `npm run preview` – Smoke-test the production bundle locally.
   - `npm run typecheck` – Run TypeScript checks and keep them passing.
3. Follow the Tailwind-first styling approach described in
   `web/scene-editor/README.md`. Avoid introducing ad-hoc CSS files unless the
   design system truly requires it.
4. Capture updated screenshots whenever a change affects rendered UI. Use the
   repository's screenshot workflow (via the provided browser tooling) and link
   the artifact in your PR description.
5. Coordinate cross-cutting changes with the Python backend when adjusting
   shared contracts (API schemas, persistence formats, etc.), updating the
   relevant docs and tests in both stacks.

## Testing & Quality Gates

> **Absolute rule:** before committing *any* change you **must** run every
> command enforced by the GitHub Actions CI workflow locally and ensure they
> pass. Skipping these checks is not acceptable.

- Unit tests use `pytest`. Run the full suite with:
  ```bash
  pytest -q
  ```
- Static typing is configured through `mypy.ini`. Check types with:
  ```bash
  mypy src
  ```
- Format the codebase with [Black](https://black.readthedocs.io/) and lint with
  [Ruff](https://github.com/astral-sh/ruff):
  ```bash
  black src tests
  ruff check src tests
  ```

All new or modified Python modules should include test coverage under `tests/`.

## Contribution & Workflow Guidelines

- Keep commits focused and use imperative present-tense messages (e.g., "Add
  persistence helper").
- Every pull request should explain the motivation, summarize the changes, and
  note follow-up work if needed.
- Reference GitHub issues when applicable (e.g., `Fixes #12`).
- Never commit secrets. Configuration that must stay local belongs in `.env`
  files (already ignored by git).
- Reviewers expect passing tests, linting, and type checks before code review.

Happy hacking and have fun exploring agent-driven storytelling!
