# Extension Guide

This guide highlights common extension points in the text adventure agent
playground and provides actionable recipes for building on the existing
infrastructure. It assumes familiarity with the runtime overview in
[`docs/architecture_overview.md`](architecture_overview.md) and supplements the
API-level reference with practical workflows.

## Story Engine Variants

The `StoryEngine` protocol defines how narrative events are produced. To create
an alternative engine:

1. Subclass or implement `StoryEngine` and provide the `propose_event` and
   `format_event` methods. Accept dependencies (content files, external services
   or planners) via the constructor so tests can inject fixtures.
2. Return `StoryEvent` objects assembled from your content. Populate the
   `choices` mapping with lower-cased command keys and descriptive labels.
3. Raise `StoryEngineError` when the engine cannot proceed, ensuring the CLI can
   surface friendly error messages.
4. Register the engine inside the CLI entry point (or a custom driver) by
   instantiating it before calling `run_cli(world_state, story_engine, ...)`.

Useful utilities:

- `textadventure.scripted_story_engine.load_scenes_from_file` loads JSON scene
  collections and validates their structure.
- `textadventure.analytics` offers reachability and quality checks that help
  verify dynamically generated scenes.

## Building Custom Agents

Agents coordinate through `textadventure.multi_agent`. Implement the
`Agent` protocol to participate in the `MultiAgentCoordinator` loop.

1. Implement `decide(self, turn: AgentTurnContext) -> AgentDecision`.
   - Use `turn.world_state` to inspect the latest state.
   - Inspect `turn.triggers` to respond to queued events from other agents.
   - Return narration, optional choices, and metadata in the decision.
2. Optionally enqueue follow-up triggers via `decision.follow_up_triggers`.
3. For agents backed by models or services, wrap external calls behind small
   helper classes so unit tests can inject deterministic doubles.

The existing `LLMStoryAgent` illustrates how to assemble prompts, manage memory
requests, and translate structured responses into decisions. For scripted NPCs,
`ScriptedStoryAgent` demonstrates deterministic branching without LLMs.

## Adding Tools for Agents

The `Tool` protocol in `textadventure.tools` lets agents augment their
capabilities through callable utilities.

1. Implement a subclass of `Tool` with a unique `name` and `description`.
2. Override `async def run(self, input: ToolInput) -> ToolResult` to perform the
   desired behaviour.
3. Register the tool with the agent (for example, pass a list of tool instances
   to `LLMStoryAgent`). Agents decide when to invoke them during prompt
   execution.
4. Extend analytics or transcript logging if tool outputs should be visible in
   debug logs.

The `KnowledgeBaseTool` offers an example mapping commands to lore lookups.

## Extending LLM Provider Support

Adapters under `textadventure.llm_providers` wrap hosted and local model APIs.
To add a new provider:

1. Implement a factory function that returns an object satisfying `LLMClient`.
   Providers typically subclass `BaseLLMClient` to reuse request/response
   helpers.
2. Populate `LLMClient.capabilities` so downstream agents can negotiate features
   like streaming or function calling.
3. Translate provider-specific exceptions via `classify_llm_error` so callers
   receive consistent error types.
4. Register the adapter with `LLMProviderRegistry.register("provider-id", factory)`
   so it can be referenced by CLI flags or configuration files.
5. Add regression tests that exercise request translation, response parsing, and
   error scenarios with mocked SDK clients.

## Persistence and Session Storage

The CLI delegates save/load behaviour to `SessionStore` implementations.

1. Implement `SessionStore` and return a `SessionSnapshot` from
   `load(session_id)`. Raise `SessionNotFoundError` for missing saves.
2. Reuse `FileSessionStore` as a reference for serialising world state, memory
   logs, and transcript metadata.
3. Update the CLI argument parser (in `src/main.py`) to register new
   persistence backends or flags. Document any environment variables required.

## CLI and Tooling Enhancements

Many workflows layer on top of the CLI helpers in `src/main.py` and supporting
modules:

- Extend `register_default_commands` to add new debug or utility commands.
- Surface analytics or validation summaries by composing helpers from
  `textadventure.analytics` or `textadventure.search`.
- When introducing long-running operations, update transcript logging so that
  operator feedback remains observable.

## Documentation and Testing Tips

- Mirror examples in the README and docs to keep user journeys accurate.
- Add unit tests under `tests/` for every new extension point. Prefer deterministic
  fixtures over network calls.
- Update `TASKS.md` with follow-up work, open questions, or future enhancements
  discovered while extending the system.

With these patterns the text adventure playground can accommodate richer story
engines, collaborative agents, and domain-specific tooling without compromising
on determinism or developer ergonomics.
