# Feature Reference

This guide catalogues the major features exposed by the text adventure
framework so that players, designers, and integrators can quickly discover what
is available and where to look next.

## Interactive CLI Adventure

- The CLI welcomes players, prints the current story beat, and accepts free-form
  input until the narrative reaches a natural ending.【F:src/main.py†L70-L215】
- Built-in commands include `save <id>`, `load <id>`, and `status`, providing
  quick persistence controls and a live snapshot of the world, queued agent
  messages, and known save files.【F:src/main.py†L139-L212】
- Command-line flags configure persistence, transcript logging, and LLM
  co-narrators (see `--session-dir`, `--log-file`, `--llm-provider`,
  `--llm-config`, and repeated `--llm-option key=value`).【F:src/main.py†L218-L268】

## Multi-Agent Narration & LLM Integration

- Adventures are orchestrated through `MultiAgentCoordinator`, which merges the
  primary scripted narrator with optional secondary agents while preserving
  their narration, metadata, and queued follow-up triggers.【F:src/textadventure/multi_agent.py†L167-L269】
- Passing `--llm-provider` or `--llm-config` adds an `LLMStoryAgent` secondary
  narrator that prompts an LLM, enriches the story with contextual memory, and
  annotates metadata such as generation time and model identifiers.【F:src/main.py†L301-L360】【F:src/textadventure/llm_story_agent.py†L35-L170】
- The provider registry lets the CLI resolve built-in adapters (OpenAI,
  Anthropic, Cohere, Hugging Face TGI, llama.cpp) or dynamic import paths while
  safely parsing CLI/JSON configuration options.【F:src/textadventure/llm_provider_registry.py†L29-L132】【F:src/textadventure/llm_providers/__init__.py†L12-L24】

## World State & Memory

- `WorldState` tracks the current location, inventory, and history, and offers
  helpers to mutate each component while recording meaningful events.【F:src/textadventure/world_state.py†L11-L110】
- Every story observation and player action is mirrored into the attached
  `MemoryLog`, enabling agents to query recent actions or observations and to
  retrieve tagged memories.【F:src/textadventure/world_state.py†L111-L135】【F:src/textadventure/memory.py†L33-L136】

## Persistence & Transcript Logging

- `SessionSnapshot`, `InMemorySessionStore`, and `FileSessionStore` capture the
  full world state (including memory) and restore it later, while enforcing
  validated session identifiers.【F:src/textadventure/persistence.py†L15-L166】
- The CLI can stream transcripts to disk through `TranscriptLogger`, recording
  narration, player input, choices, and metadata for each turn when
  `--log-file` is supplied.【F:src/main.py†L25-L67】【F:src/main.py†L346-L360】

## Tools & Knowledge Bases

- Tools extend agent capabilities via the `Tool` abstraction, returning
  structured `ToolResponse` objects with narration and metadata.【F:src/textadventure/tools.py†L27-L78】
- `KnowledgeBaseTool` ships as an example lookup helper that validates topics,
  lists available entries, and provides friendly feedback when a query is
  missing or unknown.【F:src/textadventure/tools.py†L81-L152】

## Data-Driven Scripted Adventures

- `ScriptedStoryEngine` loads scenes from JSON definitions (or bundled defaults)
  and enforces validation rules for descriptions, choices, and transitions so
  designers can iterate without editing Python code.【F:src/textadventure/scripted_story_engine.py†L1-L200】
- Scene loaders also accept optional `Tool` integrations, enabling scripted
  commands to trigger knowledge base lookups or future tool extensions.【F:src/textadventure/scripted_story_engine.py†L12-L15】

## Search & Editing Utilities

- The search module provides structured text search, replace, and reference
  detection across scene descriptions, choices, transitions, and conditional
  overrides—handy for large adventures and editor integrations.【F:src/textadventure/search.py†L1-L200】

## Analytics & Quality Reports

- Run `python -m textadventure.analytics` to compute complexity metrics,
  content distribution summaries, reachability, item flow, and quality checks
  for any JSON scene file (defaulting to the bundled demo).【F:src/textadventure/analytics.py†L1011-L1072】
- Use `compare_adventure_variants` with `format_ab_test_report` to A/B test two
  scene collections, surfacing metric deltas plus added/removed items and
  history records between variants.【F:src/textadventure/analytics.py†L889-L1034】

Refer back to the README and the other documents in `docs/` for deep dives on
getting started, best practices, multi-agent orchestration, and troubleshooting.
