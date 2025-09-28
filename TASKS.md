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
- [ ] Extend the memory system so agents can request recent observations/actions as part of their prompts, with configuration for how much history to include.
- [ ] Provide integration tests (or golden transcripts) that exercise a hybrid scripted + LLM-backed coordinator using deterministic fixtures.

## Priority 7: Observability & Tooling
- [ ] Add transcript logging options to the CLI (e.g., `--log-file`) that capture narration, player input, and agent metadata for debugging sessions.
- [x] Introduce a debug command (such as `status`) that prints the active location, inventory summary, queued agent messages, and pending saves.
  - [x] Provide a coordinator debug snapshot with visibility into queued messages.
  - [x] Surface the world/persistence details through a CLI `status` command and cover it with tests.
- [ ] Set up a continuous integration workflow (GitHub Actions) to run tests, type checks, and linting on each push.
