# Initial Development Tasks

This document captures recommended starting tasks for building out the text-adventure agent framework. Items are grouped by priority so we can tackle the highest-impact work first.

## Priority 0: Environment Baseline
- [x] Create a minimal `src/main.py` entry point that can be executed after dependency installation.
- [x] Configure a package structure under `src/` (e.g., `src/textadventure/__init__.py`).
- [x] Add basic test scaffolding in `tests/` (at least one placeholder test verifying the package imports).
- [x] Confirm linting and formatting commands (`black`, `ruff`) run cleanly on the scaffolded code. *(Added `pytest.ini` to expose the `src/` layout and reformatted existing modules so Black and Ruff both pass.)*

## Priority 1: Core Framework Skeleton
- [x] Implement a `WorldState` object responsible for tracking locations, inventory, and history.
- [x] Design an interface for a `StoryEngine` component that can propose narrative events based on the world state.
- [x] Provide an abstraction around LLM calls (e.g., `LLMClient`) that can be mocked during tests.
- [x] Draft a simple command loop (CLI) that takes player input and routes it through the story engine.
- [x] Create an initial concrete `StoryEngine` implementation that returns scripted events for testing the loop.

## Priority 2: Persistence & Memory
- [x] Define how game sessions will be persisted (in-memory first, followed by optional file-based persistence).
- [x] Introduce a lightweight memory mechanism so the agent can recall past actions and player choices. *(Implemented `MemoryLog` utilities, wired into the world state, and surfaced via a scripted "recall" command.)*

## Priority 3: Testing & Tooling Enhancements
- [x] Write unit tests covering the world state mutations and narrative branching logic.
- [x] Set up fixtures or mocks for LLM interactions to keep tests deterministic. *(Added reusable `MockLLMClient` pytest fixtures for queuing scripted responses.)*
- [x] Integrate static type checking with `mypy` and document the workflow. *(Added `mypy.ini`, updated developer docs, and
  tracked the dependency in `requirements.txt`. Setting up CI remains a future improvement.)*
- [x] Add smoke tests for the CLI once the interactive loop is implemented. *(Introduced `tests/test_cli.py` to simulate player commands and verify graceful termination scenarios.)*

## Priority 4: Stretch Goals
- [x] Explore integrating external tools (e.g., knowledge bases or calculators) the agent can invoke during gameplay.
  - [x] Define a lightweight tool abstraction and document how tools are registered with a story engine.
  - [x] Provide an initial knowledge-base tool that surfaces lore lookups through scripted commands.
  - [x] Add automated tests covering the new tool flow and update user-facing guidance where appropriate.
- [x] Investigate saving/loading checkpoints for long-running adventures.
  - [x] Add CLI commands to save and load sessions using the persistence layer.
  - [x] Extend persistence snapshots to cover memory and provide helpers for applying them.
  - [x] Add automated tests demonstrating a save/load round-trip through the CLI.
- [x] Evaluate multi-agent orchestration for NPC behaviors or parallel storylines.
  - [x] Survey the existing single-agent architecture to identify integration points for orchestrating multiple agents.
  - [x] Draft a design proposal describing a coordinator component, message flows, and how NPC agents might plug into the story engine.
  - [x] Prototype the coordinator interfaces and stub implementations to validate the design with the scripted engine. *(Added a `MultiAgentCoordinator` with a `ScriptedStoryAgent` adapter and regression tests covering secondary narration merging.)*
  - [x] Extend the coordinator to route queued agent messages between turns once richer NPC behaviour is introduced. *(Coordinator now drains message queues each turn, targets recipients, and defers newly queued triggers to the following round with regression coverage.)*
  - [x] Outline testing strategies (unit and integration) to ensure deterministic behaviour with multiple agents. *(Documented layered unit, integration, and tooling plans in `docs/multi_agent_orchestration.md`.)*

Revisit this backlog as soon as the initial scaffolding is in place so we can refine upcoming milestones based on early feedback.

## Priority 5: Data-Driven Narrative Expansion
- [x] Externalise the scripted scenes into structured data files (e.g., YAML or JSON) so adventures can be edited without touching code while retaining sensible defaults for the demo.
  - [x] Extract the current hard-coded demo scenes into a reusable data file checked into the repo.
  - [x] Update `ScriptedStoryEngine` so it can load scenes from structured data and still provide a default demo set.
  - [x] Refresh tests and docs to cover the data-driven scene workflow.
- [x] Add validation helpers that load the scene definitions, ensure commands are unique, verify transition targets exist, and surface descriptive errors with unit tests.
  - [x] Add validation checks for duplicate choice commands and unknown transition targets when loading scenes.
  - [x] Cover validation failure scenarios with dedicated unit tests.
- [x] Document the data format and authoring workflow in `docs/` and update the README so contributors can build new adventures quickly. *(Added `docs/data_driven_scenes.md` and linked guidance from the README.)*

## Priority 6: Generative Agent Integration
- [x] Implement an `LLMStoryAgent` that wraps `LLMClient`, assembles prompts from the world state, and can participate in the `MultiAgentCoordinator` turn loop.
  - [x] Build a structured prompt generator that summarises the world state and trigger context for the LLM.
  - [x] Parse JSON responses from the LLM into `StoryEvent` instances with validation.
  - [x] Cover the agent with unit tests demonstrating prompt construction and error handling.
- [x] Extend the memory system so agents can request recent observations/actions as part of their prompts, with configuration for how much history to include. *(Added `MemoryRequest` for triggers, debug visibility, and overrides in `LLMStoryAgent` with regression tests.)*
- [x] Provide integration tests (or golden transcripts) that exercise a hybrid scripted + LLM-backed coordinator using deterministic fixtures.
  - [x] Add an integration test that runs the multi-agent coordinator with the scripted primary agent and an LLM-driven secondary agent, asserting the merged narration, choices, and metadata.

## Priority 7: Observability & Tooling
- [x] Add transcript logging options to the CLI (e.g., `--log-file`) that capture narration, player input, and agent metadata for debugging sessions.
  - [x] Outline transcript logging format and captured fields.
  - [x] Implement the CLI `--log-file` flag with a structured transcript writer.
  - [x] Add regression tests and documentation covering the logging workflow.
- [x] Introduce a debug command (such as `status`) that prints the active location, inventory summary, queued agent messages, and pending saves.
  - [x] Provide a coordinator debug snapshot with visibility into queued messages.
  - [x] Surface the world/persistence details through a CLI `status` command and cover it with tests.
- [x] Set up a continuous integration workflow (GitHub Actions) to run tests, type checks, and linting on each push. *(Added a GitHub Actions pipeline executing pytest, mypy, Ruff, and Black on pushes and pull requests.)*

## Priority 8: LLM Framework Integrations
- [x] Expand the generic `LLMClient` abstraction so it can expose provider capabilities (streaming, function calling, tool APIs) in a uniform schema across integrations.
  - [x] Define capability data structures capturing streaming, function-calling, and tool invocation metadata in a reusable format.
  - [x] Extend the `LLMClient` interface to surface capabilities and update existing implementations/mocks to advertise their support levels.
  - [x] Add unit tests covering capability negotiation to ensure providers gracefully degrade when a feature is unsupported.
  - [x] Document the canonical interface in developer docs and surface configuration examples for advanced options like temperature, caching, and safety filters.
- [x] Implement adapters for popular online providers (e.g., OpenAI, Anthropic, Cohere) that wrap their SDKs and map responses to the generic interface.
  - [x] Implement an OpenAI chat completion adapter that conforms to ``LLMClient``.
  - [x] Implement an Anthropic messages adapter that conforms to ``LLMClient``.
  - [x] Implement a Cohere chat adapter that conforms to ``LLMClient``.
  - [x] Cover the new adapters with targeted unit tests and usage documentation.
- [x] Provide retry, rate limiting, and error classification helpers that can be reused across adapters.
  - [x] Define reusable error categories and a classifier utility for mapping provider exceptions.
  - [x] Implement a configurable retry policy with exponential backoff and optional jitter.
  - [x] Add a shared fixed-interval rate limiter that adapters can reuse to throttle requests.
  - [x] Cover the new helpers with deterministic unit tests.
- [x] Add integration tests using recorded responses or fixtures to validate prompt/response translation and error handling.
  - [x] Replay recorded transcript fixtures to assert prompts, choices, and metadata merge correctly.
  - [x] Cover misconfigured fixture payloads to verify descriptive error handling from LLMStoryAgent.
- [x] Implement adapters for local runtimes (e.g., Hugging Face Text Generation Inference, llama.cpp servers) so self-hosted models can plug into the same flow.
  - [x] Document setup instructions and configuration flags required to target each local runtime.
  - [x] Add smoke tests or mocks verifying adapters handle streaming, chunked responses, and offline failure scenarios.
- [x] Create a provider registry that loads adapters dynamically based on configuration files or CLI options.
  - [x] Define an `LLMProviderRegistry` that handles registering and resolving provider factories.
  - [x] Support instantiating providers from configuration mappings (e.g., parsed config files).
  - [x] Support instantiating providers from CLI-style option strings for manual selection.
  - [x] Cover the registry behaviour with automated tests, including dynamic import and error handling.
  - [x] Update the CLI and coordinator wiring so adventures can select LLM providers at runtime.
    - [x] Add CLI flags for selecting an LLM provider and passing option key/value pairs.
    - [x] Instantiate LLM-backed agents via the provider registry when configured and integrate them with the coordinator.
    - [x] Document the workflow and add regression tests covering provider selection.
  - [x] Ensure registry lookups and adapter instantiation are covered by tests, including misconfiguration handling. *(Added coverage for dynamic import errors, invalid identifiers, and duplicate CLI options to assert descriptive failures.)*
  - [x] Support loading provider configuration from JSON files and exposing a matching CLI flag. *(Added `LLMProviderRegistry.create_from_config_file`, CLI wiring, tests, and documentation.)*

## Priority 9: Scripted Demo Worldbuilding
- [x] Plan an expanded narrative arc that showcases branching paths, inventory gating, and optional side objectives. *(Documented in the "Planned Narrative Expansion" section of `docs/data_driven_scenes.md`.)*
  - [x] Sketch a location graph covering at least three distinct regions plus connecting transitional scenes.
  - [x] Identify key items, puzzle locks, and narrative beats that can be expressed purely through the JSON schema.
- [ ] Extend `src/textadventure/data/scripted_scenes.json` with the new regions, ensuring consistent descriptions, commands, and transitions.
  - [ ] Introduce multi-step objectives (e.g., fetch quests or combination puzzles) that require revisiting earlier locations.
  - [ ] Add optional flavour interactions so the demo highlights lore lookups, journal entries, and memory recall hooks.
- [ ] Update scripted-engine tests and fixtures to cover the expanded scene graph and any new command patterns.
  - [ ] Add regression coverage validating transition targets, required items, and failure messages for gated actions.
  - [ ] Refresh golden transcripts (if any) so the CLI demo walkthrough exercises the broader storyline.
- [ ] Document the enhanced demo in `docs/data_driven_scenes.md`, including a high-level map, quest summaries, and authoring tips for further expansion.
