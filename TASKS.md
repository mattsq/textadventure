# Initial Development Tasks

This document captures recommended starting tasks for building out the text-adventure agent framework. Items are grouped by priority so we can tackle the highest-impact work first.

## Priority 0: Environment Baseline
- [x] Create a minimal `src/main.py` entry point that can be executed after dependency installation.
- [x] Configure a package structure under `src/` (e.g., `src/textadventure/__init__.py`).
- [x] Add basic test scaffolding in `tests/` (at least one placeholder test verifying the package imports).
- [ ] Confirm linting and formatting commands (`black`, `ruff`) run cleanly on the scaffolded code.

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
- [ ] Set up fixtures or mocks for LLM interactions to keep tests deterministic.
- [ ] Consider integrating type checking (e.g., `mypy`) and continuous integration workflows (GitHub Actions).
- [ ] Add smoke tests for the CLI once the interactive loop is implemented. (The scripted engine now supports manual runs.)

## Priority 4: Stretch Goals
- [ ] Explore integrating external tools (e.g., knowledge bases or calculators) the agent can invoke during gameplay.
- [ ] Investigate saving/loading checkpoints for long-running adventures.
- [ ] Evaluate multi-agent orchestration for NPC behaviors or parallel storylines.

Revisit this backlog as soon as the initial scaffolding is in place so we can refine upcoming milestones based on early feedback.
