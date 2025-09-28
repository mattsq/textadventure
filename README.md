# Text Adventure Agent Playground

This repository hosts an experimental text-adventure framework that explores how autonomous agents can narrate, plan, and react to player input.  The current implementation ships with a scripted demo adventure plus primitives for building richer multi-agent story engines and tooling experiments.

## Highlights

- **World modelling** – `WorldState` tracks locations, actors, inventory, memories, and player actions.
- **Story engines** – the `StoryEngine` protocol defines how narrative beats are proposed; the included `ScriptedStoryEngine` delivers a deterministic storyline that is easy to extend.
- **Multi-agent orchestration** – `MultiAgentCoordinator` lets several agents (LLM-backed or scripted) take turns responding to the player.
- **Session persistence** – `FileSessionStore` enables save/load checkpoints directly from the CLI demo.
- **Tooling hooks** – `KnowledgeBaseTool` and base `Tool` interfaces illustrate how agents can extend their capabilities.

## Repository Layout

```
src/
  main.py                # CLI entry point for the sample adventure
  textadventure/
    __init__.py
    llm.py               # LLM client abstractions
    memory.py            # Memory log utilities
    multi_agent.py       # Agent coordination primitives
    persistence.py       # Session snapshot + storage helpers
    scripted_story_engine.py
    story_engine.py      # Story event interfaces
    tools.py             # Tool interface & knowledge base example
    world_state.py       # Core world data model

docs/                    # Design notes and experiments
tests/                   # Pytest suite covering the package
```

Additional project planning notes live in [`TASKS.md`](TASKS.md).

## Getting Started

1. Install Python 3.9 or newer.
2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Launch the demo adventure:
   ```bash
   python src/main.py
   ```
   Use `python src/main.py --help` to discover save/load options.

## Testing and Quality Checks

Run the automated checks from the repository root:

```bash
pytest -q          # unit tests
mypy src           # type checking
black src tests    # code formatting
ruff src tests     # linting
```

## Contributing

Read the detailed contributor guidelines in [Agents.md](Agents.md).  Pull requests should include passing tests, type checks, and linting, and explain the motivation behind the change.  Issues and design ideas are always welcome!
