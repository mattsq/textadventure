# Agents Guide

## Repository Purpose

This project prototypes a small framework for running text adventures that are
orchestrated by autonomous agents. The codebase ships with a scripted demo
experience plus the building blocks for experimenting with multi-agent
coordination, tool use, LLM-backed storytellers, and session persistence.

## Key Components

The `src/` directory contains the runtime code published as the
`textadventure` package:

- **`main.py`** – CLI entry point that wires the world state, story engine,
  multi-agent coordinator, transcript logging, and optional session
  persistence together.
- **`textadventure/world_state.py`** – data model representing locations,
  actors, inventory, observations, and remembered player actions.
- **`textadventure/memory.py`** – rolling log of agent memories and utilities
  for replaying remembered observations/actions.
- **`textadventure/story_engine.py`** – protocol defining how story events are
  generated and formatted.
- **`textadventure/scripted_story_engine.py`** – deterministic story engine
  used by the demo adventure, including helpers for loading JSON scenes.
- **`textadventure/multi_agent.py`** – lightweight coordinator that lets
  multiple agents take turns responding to player input while exposing debug
  metadata.
- **`textadventure/llm_story_agent.py`** – adapter that routes coordinator
  prompts through an LLM-backed decision-maker.
- **`textadventure/llm.py`** – abstractions for integrating LLM providers when
  experimenting with generative story engines.
- **`textadventure/tools.py`** – base interfaces for tool-calling agents plus a
  simple knowledge-base lookup tool.
- **`textadventure/persistence.py`** – session snapshot helpers and
  filesystem-backed storage used by the CLI save/load commands.
- **`textadventure/data/scripted_scenes.json`** – bundled demo adventure
  definition consumed by the scripted engine.

Design notes and experiments live under `docs/`, and automated tests cover the
package in `tests/`.

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
