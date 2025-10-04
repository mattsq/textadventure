# Text Adventure Agent Playground

This repository contains an experimental text-adventure framework for exploring
how autonomous agents can narrate, plan, and react to player input. The current
implementation ships with a playable scripted demo while exposing the building
blocks needed to experiment with multi-agent coordination, tool use, and LLM
integration.

## Highlights

- **Interactive CLI demo** – `src/main.py` wires the story engine, world state,
  persistence, optional transcript logging, and the LLM provider registry into a
  small playable loop.
- **Rich world modelling** – `WorldState` tracks locations, actors, inventory,
  remembered observations, and player actions.
- **Story engines** – the `StoryEngine` protocol defines how narrative beats
  are proposed; `ScriptedStoryEngine` provides a deterministic storyline that
  is easy to extend or replace.
- **Multi-agent orchestration** – `MultiAgentCoordinator` coordinates one or
  more `Agent` implementations. The bundled `ScriptedStoryAgent` narrates the
  demo adventure, while `LLMStoryAgent` shows how to route decisions through an
  LLM-backed actor.
- **Data-driven content** – the sample adventure reads its locations from
  `textadventure/data/scripted_scenes.json`, allowing narrative tweaks without
  touching Python code.
- **Tooling hooks** – `Tool` and `KnowledgeBaseTool` illustrate how agents can
  extend their capabilities beyond pure text generation.
- **Provider registry** – `LLMProviderRegistry` and the adapters in
  `textadventure/llm_providers/` make it easy to register OpenAI, Anthropic,
  Cohere, Hugging Face Text Generation Inference, or llama.cpp co-narrators.
- **Session persistence** – `FileSessionStore` enables save/load checkpoints
  directly from the CLI demo.

## Repository Layout

```
src/
  main.py                  # CLI entry point for the sample adventure
  textadventure/
    __init__.py            # Public package surface
    llm.py                 # LLM client abstractions + helpers
    llm_provider_registry.py # CLI-friendly registry for configuring providers
    llm_providers/           # Adapters for hosted and local LLM providers
    llm_story_agent.py       # Agent bridge between the coordinator and an LLM
    memory.py                # Memory log utilities
    multi_agent.py           # Agent coordination primitives
    persistence.py           # Session snapshot + storage helpers
    scripted_story_engine.py # Deterministic engine + JSON loaders
    story_engine.py          # Story event interfaces
    tools.py                 # Tool interface & knowledge base example
    world_state.py           # Core world data model
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
  (`--log-file`). The CLI can also attach an LLM-backed secondary narrator via
  `--llm-provider`, forwarding additional key/value pairs to the selected
  provider with repeated `--llm-option` flags (for example,
  `--llm-provider openai --llm-option api_key=...`). Alternatively pass
  `--llm-config path/to/config.json` to load the provider identifier and
  options from a JSON file. A more detailed walkthrough covering environment
  setup, optional features, and troubleshooting lives in
  [`docs/getting_started.md`](docs/getting_started.md).

### Adding an LLM Co-narrator

Use the provider registry flags to experiment with LLM-driven agents alongside
the scripted narrator:

```bash
python src/main.py \
  --llm-provider my_package.llm:build_client \
  --llm-option api_key="sk-demo" \
  --llm-option model="fiction-gpt"
```

The registry resolves registered provider names or dynamic import paths of the
form `module:factory`. Each `--llm-option` supplies a `key=value` pair that is
parsed as JSON when possible (e.g., numbers, booleans) before being forwarded to
the provider factory.

JSON configuration files expose the same fields in a reusable format:

```json
{
  "provider": "openai",
  "options": {
    "api_key": "sk-demo",
    "model": "gpt-4o-mini"
  }
}
```

Launch the CLI with `--llm-config config/openai.json` to load the provider
without specifying multiple command-line flags.

### Built-in provider adapters

The registry automatically exposes adapters for a handful of hosted providers so
the CLI can be configured with concise identifiers:

| Provider | Identifier | Required options | Notes |
| --- | --- | --- | --- |
| OpenAI | `openai` | `model` (e.g., `gpt-4o-mini`) | Supports chat-completions features such as function calling and streaming. Additional `openai.OpenAI` keyword arguments (like `api_key`, `organization`, or `base_url`) can be provided via `--llm-option`. |
| Anthropic | `anthropic` | `model` (e.g., `claude-3-sonnet-20240229`), `max_tokens` | Forwards options to `anthropic.Anthropic.messages.create`. Streaming is reported as supported. |
| Cohere | `cohere` | `model` (e.g., `command-r`) | Wraps `cohere.Client.chat` and surfaces Cohere's usage metadata. |
| Hugging Face TGI | `tgi` or `text-generation-inference` | `base_url` (e.g., `http://localhost:8080`) | Sends chat prompts to a running Text Generation Inference server. Supports forwarding additional JSON parameters via `default_parameters.*` options. |
| llama.cpp | `llama-cpp` | `model_path` when the adapter constructs the client | Wraps the `llama-cpp-python` bindings. Accepts sampling options such as `n_predict`, `top_p`, etc., via `--llm-option`. |

Each adapter raises a descriptive error if the corresponding third-party SDK is
not installed locally. Supply API keys and any additional configuration through
the standard `--llm-option key=value` flag. For detailed setup instructions for
local runtimes see [`docs/local_llm_adapters.md`](docs/local_llm_adapters.md).

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
demo.
[`docs/best_practices.md`](docs/best_practices.md) captures field-tested guidance
for structuring scenes, gating progression, and preparing analytics reports.
[`docs/multi_agent_orchestration.md`](docs/multi_agent_orchestration.md)
describes how the coordinator hands off turns between scripted and LLM-backed
agents.
[`docs/advanced_techniques.md`](docs/advanced_techniques.md) collects power-user
workflows for composing multi-agent setups, wiring tools, tuning memory, and
automating analytics.
The [extension guide](docs/extension_guide.md) walks through concrete recipes
for introducing new story engines, agents, tools, persistence backends, and CLI
helpers on top of the existing runtime.
[`docs/llm_capabilities.md`](docs/llm_capabilities.md) documents the capability
schema that LLM adapters use to advertise streaming, function calling, and tool
support.

Looking for a quick catalogue of everything the framework currently supports?
See the [feature reference](docs/feature_reference.md) for an overview of the
CLI, persistence, analytics, search tooling, and more.

## Troubleshooting

Encountering issues with the CLI, persistence, or LLM integrations? Consult the
[troubleshooting guide](docs/troubleshooting.md) for common symptoms, diagnostic
steps, and recommended fixes. The checklist also covers analytics pitfalls and
tips for capturing useful debug logs when reporting bugs.

## Testing and Quality Checks

Run the automated checks from the repository root:

```bash
pytest -q          # unit tests
mypy src           # type checking
black src tests    # code formatting
ruff src tests     # linting
```

## Contributing

Read the detailed contributor guidelines in
[`docs/contributing.md`](docs/contributing.md) alongside the maintainer notes in
[Agents.md](Agents.md). Pull requests should include passing tests, type checks,
and linting, and explain the motivation behind the change. Issues and design
ideas are always welcome!
