# Text Adventure Agent Playground

This repository hosts an experimental text-adventure framework that explores how autonomous agents can narrate, plan, and react to player input.  The current implementation ships with a scripted demo adventure plus primitives for building richer multi-agent story engines and tooling experiments.

## Highlights

- **World modelling** – `WorldState` tracks locations, actors, inventory, memories, and player actions.
- **Story engines** – the `StoryEngine` protocol defines how narrative beats are proposed; the included `ScriptedStoryEngine` delivers a deterministic storyline that is easy to extend.
- **Data-driven demo scenes** – the sample adventure reads its locations from `textadventure/data/scripted_scenes.json`, making narrative tweaks possible without touching Python code.
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
    data/
      scripted_scenes.json  # Bundled demo adventure definition
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
   Use `python src/main.py --help` to discover save/load options. Pass
   `--log-file transcript.txt` to record a debugging transcript that captures
   narration, player input, and any agent metadata emitted during the session.

## Customising the Demo Adventure

The bundled `ScriptedStoryEngine` now loads its scenes from the JSON file at
`textadventure/data/scripted_scenes.json`. Copy that file to craft new
locations, choices, and transitions, then load it with
`textadventure.load_scenes_from_file` when constructing a custom engine:

```python
from textadventure import ScriptedStoryEngine, WorldState, load_scenes_from_file

scenes = load_scenes_from_file("my_custom_adventure.json")
engine = ScriptedStoryEngine(scenes=scenes)

world = WorldState()
print(engine.propose_event(world).narration)
```

Running the CLI with this engine lets designers iterate on adventures without
changing the Python source. See
[`docs/data_driven_scenes.md`](docs/data_driven_scenes.md) for a full breakdown
of the JSON schema, validation rules, and tips for wiring custom files into the
demo.

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
