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

## Frontend Stack Rationale

The React-based scene editor extends the runtime architecture with a modern
web toolchain tuned for rapid authoring. The stack choices optimise developer
experience and runtime characteristics:

- **Vite** – Provides instant local feedback through lightning-fast hot module
  replacement, typed environment variable support, and production builds that
  mirror the module graph expected by our static hosting targets. Vite's plugin
  ecosystem also unlocks Markdown-driven documentation previews and API client
  codegen without heavyweight bundler configuration.
- **React** – Aligns with the component model documented in
  `docs/frontend_component_catalog.md`, enabling composable UI primitives that
  map directly to backend resources (projects, scenes, collaboration sessions).
  React's declarative state model pairs with React Query and Zustand to isolate
  server mutations from UI chrome, keeping the authoring experience predictable
  even during realtime collaboration.
- **Tailwind CSS** – Reinforces a utility-first design language that keeps the
  component library consistent with accessibility guidance noted in
  `web/scene-editor/AGENTS.md`. Tailwind's design tokens mirror the CLI's
  colour and typography scale, simplifying shared branding across
  documentation, the editor, and generated transcripts.

These choices deliberately minimise bespoke configuration so that backend and
tooling contributors can reason about the frontend without deep web-specific
expertise. They also align with CI expectations (Node 18+, lint/typecheck
commands) captured in the repository's contributor guides.

## Shared Terminology

Cross-team collaboration relies on a consistent vocabulary spanning the CLI and
scene editor surfaces. The following terms are used across documentation,
runtime code, and web tooling:

- **Scene graph** – Directed network of nodes representing narrative beats and
  conditional transitions. Stored according to `docs/web_editor_schema.md` and
  visualised in the editor's graph canvas.
- **Node** – A single playable moment containing narration, triggers, and
  outcomes. Nodes render as cards in the detail side panel and as events within
  CLI transcripts via `StoryEngine.format_event`.
- **Transition** – Edge connecting nodes, potentially gated by conditions or
  player inventory checks. Transitions inform both runtime validation utilities
  and the editor's pathfinding helpers.
- **Project** – Collection of scenes, assets, and collaboration metadata. The
  backend's session catalogue API exposes projects; the editor dashboard lists
  them as entry points for authors.
- **Collaboration session** – Realtime editing context that tracks presence,
  comments, and change history. Powered by websocket events described in
  `docs/web_editor_api_spec.md` and surfaced through the collaboration hub UI.

Maintaining shared definitions ensures that documentation, runtime logs, and
feature roadmaps communicate intent without ambiguity as new contributors join
the project.

Refer to the automated tests in `tests/` for executable usage examples; the
suite covers CLI flows, scene validation, analytics, coordinator behaviour, and
LLM prompting.
