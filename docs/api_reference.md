# Text Adventure API Reference

This document summarises the primary modules, classes, and functions that make up the
text adventure runtime. It highlights how each piece fits into the broader system so
you can navigate the codebase quickly when building features or integrating external
services.

## Core State & Memory
- **`WorldState` (`textadventure.world_state`)** – Tracks the player's location,
  inventory, event history, and structured memory. Helper methods validate inputs,
  update the world, and mirror notable events in the history log. It also exposes
  helpers for recording and retrieving recent actions or observations via the
  bundled `MemoryLog` instance. `WorldState` is the central context object that gets
  threaded through story engines, agents, and persistence layers.
- **`MemoryLog`, `MemoryEntry`, and `MemoryRequest` (`textadventure.memory`)** –
  Provide a structured memory system for agents. `MemoryLog` stores tagged entries,
  offers recent-history queries, and supports tag-based lookup. `MemoryRequest`
  instances allow agents to request custom action/observation limits, while
  `MemoryEntry` captures each stored memory.

## Story Engines & Narrative Data
- **`StoryEngine`, `StoryEvent`, and `StoryChoice` (`textadventure.story_engine`)** –
  Define the core interface for producing narrative beats. `StoryEngine.propose_event`
  accepts a `WorldState` (and optional player input) and returns a `StoryEvent`
  containing narration, optional choices, and metadata. The base class also provides
  `format_event` for turning an event into printable text.
- **`ScriptedStoryEngine` (`textadventure.scripted_story_engine`)** – Loads structured
  scene definitions, evaluates conditional narration, updates the `WorldState`, and
  emits validated `StoryEvent` instances. Helper dataclasses encapsulate scene
  transitions, conditional overrides, and narration summaries for commands such as
  `status`, `inventory`, and `recall`.
- **Scene loading utilities (`load_scenes_from_mapping`, etc.)** – Parse JSON
  definitions into strongly typed scene structures, validate commands and transitions,
  and surface descriptive exceptions for malformed data.

## Multi-Agent Coordination
- **`MultiAgentCoordinator` (`textadventure.multi_agent`)** – Implements the
  orchestrator used to merge outputs from multiple agents while preserving turn order.
  The coordinator queues agent-to-agent triggers, handles first-turn initialisation,
  and produces a single `StoryEvent` each round.
- **Agent data structures** – `AgentTrigger`, `AgentTurnResult`, and
  `QueuedAgentMessage` standardise how triggers, events, and pending messages flow
  through the coordinator. `CoordinatorDebugState` snapshots queued messages for the
  CLI `status` command and other diagnostics.
- **`ScriptedStoryAgent` adapter** – Wraps any `StoryEngine` implementation so it can
  participate in the coordinator loop while responding to player input triggers.

## LLM Abstractions & Providers
- **`LLMMessage`, `LLMResponse`, and capability helpers (`textadventure.llm`)** –
  Define the generic contract for exchanging messages with language models,
  including capability discovery (`LLMCapabilities`, `LLMCapability`, and
  `LLMToolDescription`). Providers and tests rely on these immutable data classes to
  negotiate features like streaming, function calling, and tool invocation.
- **`LLMStoryAgent` (`textadventure.llm_story_agent`)** – Bridges the story engine
  protocol with an LLM client. It composes prompts from the world state, honours
  `MemoryRequest` scopes, parses structured responses into `StoryEvent` objects, and
  emits coordinator-friendly metadata.
- **`LLMProviderRegistry` and provider adapters** – The registry (`textadventure.llm_provider_registry`)
  exposes CLI-friendly lookups for configuring providers at runtime. Individual
  adapters in `textadventure.llm_providers` implement the `LLMClient` protocol and
  surface provider-specific capability metadata while sharing retry and error
  handling utilities.

## Persistence & Transcript Logging
- **`SessionSnapshot` and `SessionStore` (`textadventure.persistence`)** – Capture,
  serialise, and restore `WorldState` objects. File-backed stores enable CLI save and
  load workflows, while in-memory stores support testing.
- **CLI runtime (`src/main.py`)** – `run_cli` wires together a story engine,
  world state, optional session store, and transcript logging. The embedded
  `TranscriptLogger` records narration, choices, metadata, and player commands for
  debugging, while commands such as `help`, `tutorial`, `status`, `save`, and `load`
  expose runtime management features.

## Tooling, Analytics, and Search
- **Tool abstractions (`textadventure.tools`)** – Define the base `Tool` interface
  and ship a reference `KnowledgeBaseTool` used by the scripted engine for lore
  lookups. Tool results can be surfaced through agent metadata or narration.
- **Analytics helpers (`textadventure.analytics`)** – Compute adventure metrics such
  as complexity, reachability, content distribution, and quality heuristics.
  Utilities return structured summaries suitable for CLI reporting or API exposure.
- **Search utilities (`textadventure.search`)** – Provide indexed text search across
  scenes with field-type and validation filtering. Results expose per-field spans to
  power editor experiences and automated audits.

## HTTP API Surface
- **FastAPI application (`textadventure.api.app`)** – Offers programmatic access to
  bundled scene data and analytics. `SceneService` returns paginated summaries with
  validation metadata, produces Git-style diffs for uploaded datasets, `SceneSearchResponse`
  powers full-text queries, and helper parsers validate query parameters for
  field-type and validation filters. The API also exposes project-management
  endpoints backed by `ProjectService`, allowing tooling to discover registered
  adventure datasets, retrieve their scene payloads alongside checksum and
  version metadata, enumerate project assets through structured listings, and
  download individual asset files with appropriate content headers for editor
  previews.
  `ProjectTemplateService` lists reusable project templates and provides an
  instantiation endpoint that materialises a new project directory by copying the
  template scenes and metadata.
- **Pydantic response models** – `SceneSummary`, `SceneSearchResultResource`, and
  supporting models normalise the API payloads consumed by prospective web tools or
  external services. Recent additions include `ProjectAssetResource` and
  `ProjectAssetListResponse`, which document the assets bundled with a project so
  editors can surface file metadata, MIME types, and modification timestamps.
- **Deployment settings (`textadventure.api.settings.SceneApiSettings`)** – Reads
  environment variables such as `TEXTADVENTURE_SCENE_PATH`,
  `TEXTADVENTURE_SCENE_PACKAGE`, `TEXTADVENTURE_SCENE_RESOURCE`,
  `TEXTADVENTURE_BRANCH_ROOT`, `TEXTADVENTURE_AUTOMATIC_BACKUP_DIR`,
  `TEXTADVENTURE_AUTOMATIC_BACKUP_RETENTION`, `TEXTADVENTURE_PROJECT_ROOT`, and
  `TEXTADVENTURE_PROJECT_TEMPLATE_ROOT` so the API can target custom scene
  datasets, branch storage directories, automatic backup locations, a project
  registry, and an optional template catalogue without code changes.

Use this reference alongside the architecture overview to dive deeper into specific
modules when extending the engine or integrating new agent capabilities.

## OpenAPI & Swagger Documentation

The FastAPI service automatically publishes a comprehensive OpenAPI specification and
interactive Swagger UI. After launching the editor API (for example via
`python -m uvicorn textadventure.api.app:create_app --factory` or the CLI `editor`
command), visit:

- **`/openapi.json`** – Machine-readable OpenAPI schema capturing all request and
  response models, tags, and error formats. This is ideal for generating client
  SDKs or running automated contract tests.
- **`/docs`** – Swagger UI that lets you explore tagged endpoints, inspect
  request/response examples, and execute calls against a running server.

Endpoints are grouped under the following tags to make exploration easier:

- **Scenes** – CRUD, validation, analytics, and import/export workflows for scripted
  scenes.
- **Scene Branches** – Snapshot management for experimental branches.
- **Search** – Full-text queries with field-type and validation filters.
- **Projects** – Project discovery plus asset and collaborator management.
- **Project Templates** – Template catalogue and instantiation helpers for spinning
  up new adventures.

Use these resources to integrate tooling, generate client libraries, or confirm the
expected payloads when extending the backend.
