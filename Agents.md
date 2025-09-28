# Agents Guide

## Overview

This repository is an experimental playground for building a text‑based adventure game using agentic tools. The aim is to explore how autonomous agents can manage and evolve a narrative world.

## Goals

- Prototype a lightweight framework where an agent orchestrates story progression.
- Experiment with large language models and tool integrations for dynamic content generation.
- Investigate memory and planning mechanisms that allow the agent to keep track of state and player choices.

## Architecture

A basic scaffolding for the agent might include:

- **World State Manager** – maintains the current location, inventory, NPC states and history.
- **Story Engine** – proposes narrative events based on the world state and player inputs.
- **LLM Interface** – wraps calls to language models for generating descriptions, dialogues and branching outcomes.
- **Interaction Layer** – provides a text‑based interface (CLI or web) for the player to interact with the agent.
- **Persistence Module** – stores session data and allows saving/loading game progress.

## Setup

Follow these steps to get your development environment ready:

1. **Prerequisites**: Install Python 3.9 or newer.
2. **Install dependencies**: In the repository root, run:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # on Windows use `.venv\Scripts\activate`
   pip install -r requirements.txt
   ```

3. **Run the project**: After installing dependencies, you can run the sample driver script to start a simple text adventure:

   ```bash
   python src/main.py
   ```

4. **Project structure**: Source code should live in the `src/` directory. Tests should live in `tests/`.

## Testing

We use `pytest` for unit tests. To run the full test suite, execute:

```bash
pytest -q
```

Tests live in `tests/` with filenames prefixed by `test_`. When adding new modules, create accompanying tests.

## Code Style & Formatting

- Follow [PEP 8](https://peps.python.org/pep-0008/) conventions.
- Use [Black](https://black.readthedocs.io/en/stable/) to auto‑format your code:

  ```bash
  black src tests
  ```

- Lint code with [Ruff](https://github.com/astral-sh/ruff) or [Flake8](https://flake8.pycqa.org/):

  ```bash
  ruff src tests
  ```

Formatting and linting should pass locally before committing.

## Commit & Pull Request Guidelines

- Write clear, concise commit messages in the present tense (e.g., “Add inventory system”).
- Each pull request should focus on a single feature or fix.
- Include context in PR descriptions: what changed, why, and any follow‑ups.
- Reference issue numbers if applicable (e.g., `Fixes #12`).

## Dependency & Security Policy

- Declare all runtime dependencies in `requirements.txt` (or `pyproject.toml` if using Poetry).
- Regularly update dependencies and review release notes for security patches.
- Do not commit secrets (API keys, credentials) to the repository. Use environment variables or a `.env` file (which is git‑ignored).

## Contributing

- Contributions are welcome from both humans and agents. Ensure your changes pass tests and linting.
- For substantial changes, open an issue to discuss the approach before starting.
