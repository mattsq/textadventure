# Text Adventure Agent Playground

This repository contains an experimental text-adventure framework for exploring
how autonomous agents can narrate, plan, and react to player input. The current
implementation ships with a playable scripted demo while exposing the building
blocks needed to experiment with multi-agent coordination, tool use, and LLM
integration.

## Highlights

- **Interactive CLI demo** – `src/main.py` wires the story engine, world state,
  persistence, and optional transcript logging into a small playable loop.
- **Rich world modelling** – `WorldState` tracks locations, actors, inventory,
  remembered observations, and player actions.
- **Story engines** – the `StoryEngine` protocol defines how narrative beats
  are proposed; `ScriptedStoryEngine` provides a deterministic storyline that
  is easy to extend or replace.
- **Multi-agent orchestration** – `MultiAgentCoordinator` coordinates one or
  more `Agent` implementations. The included `ScriptedStoryAgent` narrates the
  demo adventure, while `LLMStoryAgent` shows how to route decisions through an
  LLM-backed actor.
- **Data-driven content** – the sample adventure reads its locations from
  `textadventure/data/scripted_scenes.json`, allowing narrative tweaks without
  touching Python code.
- **Tooling hooks** – `Tool` and `KnowledgeBaseTool` illustrate how agents can
  extend their capabilities beyond pure text generation.
- **Session persistence** – `FileSessionStore` enables save/load checkpoints
  directly from the CLI demo.

## Repository Layout

```
src/
  main.py                  # CLI entry point for the sample adventure
  textadventure/
    __init__.py            # Public package surface
    llm.py                 # LLM client abstractions + helpers
    llm_story_agent.py     # Agent bridge between the coordinator and an LLM
    memory.py              # Memory log utilities
    multi_agent.py         # Agent coordination primitives
    persistence.py         # Session snapshot + storage helpers
    scripted_story_engine.py
    story_engine.py        # Story event interfaces
    tools.py               # Tool interface & knowledge base example
    world_state.py         # Core world data model
    data/
      scripted_scenes.json # Bundled demo adventure definition

docs/                      # Design notes and experiments
tests/                     # Pytest suite covering the package
TASKS.md                   # Planning notes and backlog ideas
```

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
   Run `python src/main.py --help` to discover options for enabling persistence
   (`--session-dir`, `--session-id`, `--no-persistence`) and transcript logging
   (`--log-file`).

## Customising the Demo Adventure

`ScriptedStoryEngine` loads its scenes from
`textadventure/data/scripted_scenes.json`. Copy that file to craft new
locations, choices, and transitions, then load it with
`textadventure.load_scenes_from_file` when constructing a custom engine:

```python
from textadventure import ScriptedStoryEngine, WorldState, load_scenes_from_file

scenes = load_scenes_from_file("my_custom_adventure.json")
engine = ScriptedStoryEngine(scenes=scenes)

world = WorldState()
event = engine.propose_event(world)
print(event.narration)
```

Running the CLI with this engine lets designers iterate on adventures without
changing the Python source. See
[`docs/data_driven_scenes.md`](docs/data_driven_scenes.md) for a full breakdown
of the JSON schema, validation rules, and tips for wiring custom files into the
demo. [`docs/multi_agent_orchestration.md`](docs/multi_agent_orchestration.md)
describes how the coordinator hands off turns between scripted and LLM-backed
agents.

## Testing and Quality Checks

Run the automated checks from the repository root:

```bash
pytest -q          # unit tests
mypy src           # type checking
black src tests    # code formatting
ruff src tests     # linting
```

## Contributing

Read the detailed contributor guidelines in [Agents.md](Agents.md). Pull
requests should include passing tests, type checks, and linting, and explain the
motivation behind the change. Issues and design ideas are always welcome!
