# Multi-Agent Orchestration Plan

## Overview
This document explores how to extend the current single-agent text adventure
framework to coordinate multiple autonomous agents. The goal is to allow the
player-facing story engine to collaborate with specialised non-player
characters (NPCs) or background systems that can run in parallel and enrich the
narrative.

## Current Architecture Summary
- **WorldState** keeps track of the player's location, inventory, history, and
  memory logs. It already persists key observations and player actions.
- **StoryEngine** is responsible for generating `StoryEvent` objects in response
  to the evolving world state and player input. The scripted implementation
  handles branching, tool invocation, and inventory updates.
- **Tools** provide side-channel capabilities (e.g., lore lookups) that the
  story engine can call based on player commands.
- **CLI Loop** gathers player input, records memory, and asks the story engine
  to produce the next event.

This setup assumes a single authoritative story engine that owns both narrative
logic and NPC behaviour. To support multi-agent scenarios we need a layer that
can orchestrate multiple story contributors, arbitrate their outputs, and keep
the world state consistent. The CLI demo exposes this orchestration path by
allowing an LLM-backed secondary narrator to be attached at runtime with the
`--llm-provider` flag, keeping experimentation in parity with the scripted
primary agent.

## Proposed Components
1. **Agent Interface**
   - Define an `Agent` protocol exposing `propose_event(world_state, *,
     trigger)` that mirrors the existing `StoryEngine` signature.
   - Each agent receives the shared `WorldState` along with a trigger describing
     why it was invoked (player input, timer tick, another agent's message).

2. **Coordinator**
   - Introduce a `MultiAgentCoordinator` responsible for routing triggers to
     the appropriate agent (or agents) and merging their responses.
   - The coordinator would maintain lightweight agent metadata (e.g., priority,
     subscribed triggers) and decide how to combine concurrent events. For the
     initial prototype we can keep this deterministic by running agents in a
     fixed order and composing their `StoryEvent` narrations/choices.

3. **Message Bus**
   - Define simple `AgentMessage` objects that encapsulate observations or
     intents an agent wants to broadcast. Messages can be queued on the
     coordinator so that subsequent ticks fan them out to interested agents.

4. **Adapted Story Engine**
   - Wrap the existing `StoryEngine` (scripted implementation) as a primary
     agent that handles player input and world mutations.
   - NPC agents could focus on asynchronous behaviours such as reacting to
     world state changes, offering side quests, or interrupting the narrative
     with urgent events.

## Trigger Flow
1. Player input arrives via the CLI and is recorded in `WorldState` memory.
2. The coordinator enqueues a `PlayerInput` trigger and dispatches it to the
   main story agent.
3. After the main agent produces a `StoryEvent`, the coordinator posts any
   resulting messages (e.g., "player entered room").
4. Secondary agents (NPCs, background systems) consume queued messages in a
   deterministic order. Each agent can choose to produce additional
   `StoryEvent` fragments (e.g., optional dialogue, warnings).
5. The coordinator merges the fragments into the final event that the CLI
   prints, ensuring that choices remain deduplicated and commands stay unique.

## Data Considerations
- Continue using `WorldState` as the single source of truth. Agents should
  mutate it via well-defined methods to avoid conflicts.
- Track which agent produced each narration/metadata entry so we can attribute
  content or filter it for testing.
- Store coordinator configuration alongside session persistence so that saved
  games reload the same agent roster and internal message queues.

## Testing Strategy
Ensuring deterministic behaviour across multiple agents requires layered
coverage so we can quickly pinpoint regressions.

### Unit Tests
- **Coordinator sequencing** – Stub two or more agents with scripted outputs
  and assert that the coordinator merges narrations and choices in the expected
  order regardless of trigger permutations.
- **Message queue flow** – Drive queued `AgentMessage` instances through the
  coordinator and verify that fan-out honours subscription metadata and that
  deferred messages surface on the following tick.
- **World mutations** – Use fixtures to snapshot `WorldState` before and after
  agent runs, confirming that concurrent mutations resolve predictably and
  metadata attribution is preserved.

### Integration Tests
- **CLI smoke paths** – Exercise the text loop with a coordinator hosting the
  scripted player agent plus at least one NPC agent. Validate the combined
  narration, player choices, and termination semantics remain stable across
  runs.
- **Persistence round-trips** – Save a session mid-turn while queues contain
  pending messages, reload it, and confirm the coordinator resumes with the same
  ordering guarantees.
- **Failure isolation** – Simulate an agent raising an exception and assert the
  coordinator captures it, records diagnostics, and continues processing other
  agents without duplicating output.

### Tooling & Infrastructure
- Provide pytest fixtures for constructing coordinators with configurable agent
  line-ups and scripted triggers, allowing tests to focus on behaviour rather
  than setup.
- Capture golden transcripts for complex scenarios so snapshot tests can detect
  unintended narration drift while still allowing intentional updates via
  reviewable fixtures.

Together these layers give us confidence that the orchestrator behaves
predictably as new agent capabilities are introduced.

## Next Steps
1. **Interface Prototyping** – Create `Agent`, `AgentTrigger`, and
   `MultiAgentCoordinator` classes with deterministic sequencing and simple
   merging rules. Wrap `ScriptedStoryEngine` in an adapter that implements the
   agent interface.
2. **Test Harness Implementation** – Build out the fixtures and regression
   suites described above so future agent experiments can rely on fast,
   reproducible feedback.

## Open Questions
- How should conflicting choices be resolved? (e.g., two agents suggesting the
  same command with different descriptions)
- Do we need priority queues or time-based triggers for asynchronous agents?
- Should the coordinator be responsible for error isolation (if one agent
  fails, can the others continue)?

Addressing these will guide future iterations once the basic coordinator
prototype is in place.
