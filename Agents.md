# Agents Guide

## Repository Purpose

This project prototypes a small framework for running text adventures that are orchestrated by autonomous agents.  The codebase contains both a scripted demo experience and the building blocks for experimenting with planner/actor style agents, tool use, and session persistence.

## Key Components

The `src/` directory contains the runtime code shipped as the `textadventure` package:

- **`main.py`** – CLI entry point that wires the world state, story engine, multi-agent coordinator, and optional session persistence together.
- **`textadventure/world_state.py`** – data model representing locations, actors, inventory, observations, and remembered player actions.
- **`textadventure/memory.py`** – rolling log of agent memories and utilities for replaying remembered observations/actions.
- **`textadventure/story_engine.py`** – protocol defining how story events are generated and formatted.
- **`textadventure/scripted_story_engine.py`** – deterministic story engine used by the demo adventure.
- **`textadventure/multi_agent.py`** – lightweight coordinator that lets multiple agents take turns responding to player input.
- **`textadventure/llm.py`** – abstractions for integrating LLM providers when experimenting with generative story engines.
- **`textadventure/tools.py`** – base interfaces for tool-calling agents plus a simple knowledge-base lookup tool.
- **`textadventure/persistence.py`** – session snapshot helpers and filesystem-backed storage used by the CLI save/load commands.

Design notes and experiments are collected under `docs/`, and automated tests live in `tests/`.

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
   Use `--help` for persistence-related options like `--session-dir` and `--session-id`.

## Testing & Quality Gates

- Unit tests use `pytest`. Run the full suite with:
  ```bash
  pytest -q
  ```
- Static typing is configured through `mypy.ini`. Check types with:
  ```bash
  mypy src
  ```
- Format the codebase with [Black](https://black.readthedocs.io/) and lint with [Ruff](https://github.com/astral-sh/ruff):
  ```bash
  black src tests
  ruff src tests
  ```

All new or modified Python modules should include test coverage under `tests/`.

## Contribution & Workflow Guidelines

- Keep commits focused and use imperative present-tense messages (e.g., "Add persistence helper").
- Every pull request should explain the motivation, summarize the changes, and note follow-up work if needed.
- Reference GitHub issues when applicable (e.g., `Fixes #12`).
- Never commit secrets. Configuration that must stay local belongs in `.env` files (already ignored by git).
- Reviewers expect passing tests, linting, and type checks before code review.

Happy hacking and have fun exploring agent-driven storytelling!
