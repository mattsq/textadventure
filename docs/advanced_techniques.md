# Advanced Techniques for Power Users

This guide showcases ways to push the text adventure framework beyond the out-of-the-box demo. It highlights extensibility hooks for orchestrating multiple agents, layering in LLM narrators, integrating custom tools, curating memory, and automating analysis so experienced builders can deliver richer adventures.

## Compose Custom Multi-Agent Setups

- Treat `MultiAgentCoordinator` as the primary entry point when you want more than one narrator. Pass the scripted engine as the primary agent and register any number of secondary agents; the coordinator merges narration, choices, and metadata while keeping agent-specific keys namespaced.【F:src/textadventure/multi_agent.py†L167-L347】
- Agents can queue follow-up messages that target specific collaborators via trigger metadata. Messages are delivered on the next turn, ensuring deterministic ordering even in complex collaborations.【F:src/textadventure/multi_agent.py†L200-L293】
- Use `CoordinatorDebugState` during playtesting to inspect queued cross-agent messages and confirm routing logic before rolling out elaborate behaviours.【F:src/textadventure/multi_agent.py†L116-L270】

## Build Specialised LLM Narrators

- `LLMStoryAgent` wraps any `LLMClient`, constructs structured prompts from the world state, and enforces JSON responses. Configure the agent with a custom `system_prompt`, temperature, and memory limits to suit each model’s strengths.【F:src/textadventure/llm_story_agent.py†L35-L132】
- Each response is parsed into a `StoryEvent`, merged with provider metadata, and annotated with latency and token usage so you can monitor quality and cost during iteration.【F:src/textadventure/llm_story_agent.py†L83-L250】
- The CLI’s provider registry instantiates adapters from CLI flags or JSON config files, letting you swap providers (OpenAI, Anthropic, Cohere, Hugging Face TGI, llama.cpp) without code changes. Wrap the resulting client in `LLMStoryAgent` instances to add co-narrators on demand.【F:src/main.py†L301-L360】

## Tailor Memory and Context Windows

- `WorldState` exposes helpers for recording actions, observations, and history entries, ensuring the memory log stays in sync with major story beats.【F:src/textadventure/world_state.py†L33-L135】
- `MemoryLog` supports tagged entries, recent history queries, and filtered retrieval for agent prompts. Use `MemoryRequest` objects in queued triggers to request deeper or shallower context slices for downstream agents.【F:src/textadventure/memory.py†L33-L130】
- When persistence is enabled, snapshots capture world, history, and memory data. Use `SessionSnapshot.capture` during custom tooling (e.g., automated playtests) to checkpoint scenarios and restore them later via the `SessionStore` implementations.【F:src/textadventure/persistence.py†L15-L166】

## Wire Up Tools and Knowledge Bases

- Register additional `Tool` implementations with `ScriptedStoryEngine` via the `tools` parameter to expose slash-style commands (e.g., `guide crystals`). Tools return structured `ToolResponse` objects that are converted into story events so their narration and metadata blend seamlessly with scripted scenes.【F:src/textadventure/scripted_story_engine.py†L406-L491】
- `KnowledgeBaseTool` is a reference implementation that validates topics, offers usage hints, and emits descriptive metadata about lookup status. Mirror its approach when building domain-specific utilities such as calculators or lore encyclopedias.【F:src/textadventure/tools.py†L27-L152】

## Automate Quality Analysis & Instrumentation

- Enable transcript logging through the CLI’s `--log-file` flag to capture per-turn narration, metadata, and choices for later review or analytics pipelines.【F:src/main.py†L25-L360】
- Run `python -m textadventure.analytics` against any JSON scene file to generate complexity metrics, reachability reports, item flow summaries, and quality assessments. The CLI automatically loads the bundled demo scenes when no path is supplied, making it easy to baseline new adventures.【F:src/textadventure/analytics.py†L1011-L1072】

Keep iterating on these building blocks—layer multiple LLM agents, pipe transcripts into custom dashboards, and experiment with new tools—to craft bespoke narrative experiences tailored to your players.
