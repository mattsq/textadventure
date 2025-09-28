# Text Adventure Game (Experiment)

This repository contains an experimental text-based adventure game controlled by autonomous agents. The project explores how AI agents can manage, narrate, and evolve an interactive story.

## Project Goals

- Build a lightweight framework for agent-driven narrative progression.
- Integrate large language models and external tools to generate dynamic content.
- Experiment with memory and planning mechanisms to track world state and player choices.

## Getting Started

For detailed setup, testing and contribution instructions, see [AGENTS.md](Agents.md). In brief:

1. Ensure you have Python 3.9+ installed.
2. Install dependencies from `requirements.txt`.
3. Run the sample driver script under `src/` to launch the game.

## Development Workflow

- Format and lint the codebase with `black` and `ruff` before committing changes.
- Run the automated tests with `pytest -q`.
- Check static typing with `mypy` (configuration lives in `mypy.ini`).

We welcome contributions! Please read the contribution guidelines in `AGENTS.md` before submitting pull requests.
