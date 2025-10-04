# Architecture Overview

This document summarises how the text adventure prototype is organised, which
modules collaborate to drive the command-line experience, and where to extend
the system for new adventures or agent behaviours.

## Runtime Flow

1. **Entry point** – `src/main.py` wires the world state, story engine, optional
   persistence, optional LLM providers, and an interactive CLI loop. It prints
   story events using `StoryEngine.format_event`, handles commands such as
   `help`, `tutorial`, `save`, `load`, and `status`, and records transcripts when
   requested.
2. **World state** – `WorldState` stores the player's location, inventory,
   history, and a rolling `MemoryLog`. Helper methods validate inputs, record
   events, and expose recent actions/observations to agents.
3. **Story engines** – Runtime behaviour is driven by implementations of the
   abstract `StoryEngine` interface. Each `StoryEvent` contains narration,
   optional choices, and metadata.
4. **Persistence** – `SessionStore` implementations capture the
   `SessionSnapshot` derived from a `WorldState`, enabling saves and reloads.
5. **Transcripts** – The CLI optionally captures player input and events via
   `TranscriptLogger` for later debugging.

## Storytelling Components

- **Scripted stories** – `ScriptedStoryEngine` loads deterministic scenes from
  `textadventure/data/scripted_scenes.json`, validates them, and produces
  scripted `StoryEvent` instances. It underpins the default demo adventure and
  shares helper utilities with validation and search modules.
- **Multi-agent coordination** – `MultiAgentCoordinator` lets several agents
  contribute narration and choices each turn. It enforces primary-agent output,
  merges metadata without collisions, and routes queued `AgentTrigger`
  messages between turns.
- **LLM-backed agents** – `LLMStoryAgent` adapts the coordinator protocol for
  large-language-model responses. Prompts include relevant world state,
  optional memory slices, and downstream tool calls.
- **Memory system** – `MemoryLog` stores chronological observations and player
  actions. `MemoryRequest` allows agents to retrieve scoped slices (e.g., most
  recent actions) as part of prompt assembly.
- **Tool integration** – `textadventure.tools` defines tool protocols and ships
  a knowledge-base lookup helper so agents can enrich narration or inspect
  lore.

## LLM Provider Infrastructure

- **Provider registry** – `LLMProviderRegistry` registers adapters and parses
  CLI flags such as `--llm-provider` and repeated `--llm-option key=value`
  overrides. It builds configured clients that adhere to the shared
  `LLMClient` interface.
- **Provider adapters** – Modules under `textadventure.llm_providers` wrap
  third-party SDKs (OpenAI, Anthropic, Cohere, Hugging Face TGI, llama.cpp)
  with consistent request/response handling, error classification, retry
  policies, and rate limiting.
- **Capability metadata** – `textadventure.llm` defines reusable dataclasses
  describing provider capabilities (streaming, tool usage, function calling)
  alongside transport-agnostic request/response models.

## Data Services and Analytics

- **Validation utilities** – Scene-loading helpers perform structural
  validation (duplicate commands, unknown transitions, missing narration) and
  surface descriptive exceptions when data is inconsistent.
- **Search & reference tooling** – `textadventure.search` powers full-text
  search, filtering, and reference detection across scene content for use in
  tooling or diagnostics.
- **Analytics** – `analytics.py` computes adventure complexity, reachability,
  content distribution, and quality reports. These summaries feed both CLI
  reporting and API surfaces.
- **API layer** – `textadventure.api.app` exposes FastAPI resources for scene
  listings, full-text search, and validation metadata. Responses rely on the
  same scene-loading, analytics, and search utilities used by the CLI.

## Extensibility Paths

- **CLI orchestration** – Swap `StoryEngine` implementations or compose new
  agent combinations before calling `run_cli` for alternative gameplay loops.
- **Session backends** – Implement additional `SessionStore` flavours (e.g.,
  databases, cloud storage) by adhering to the persistence interfaces.
- **Tool ecosystem** – Register new tool classes for LLM agents to call, or
  expose runtime capabilities via agent-to-agent messages.
- **Editor integrations** – The `docs/web_editor_*` files and API endpoints
  lay groundwork for richer authoring experiences beyond the CLI.

Refer to the automated tests in `tests/` for executable usage examples; the
suite covers CLI flows, scene validation, analytics, coordinator behaviour, and
LLM prompting.
