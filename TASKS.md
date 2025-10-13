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
  - [x] Extend `src/textadventure/data/scripted_scenes.json` with the new regions, ensuring consistent descriptions, commands, and transitions. *(Introduced a post-observatory resonant bridge and sky sanctum finale to round out the storyline.)*
  - [x] Add region hubs for the Sunken Bastion and Aether Spire that connect the planned scene graph.
  - [x] Populate optional detours (`scavenger-camp`, `ranger-lookout`, side rooms) with unique interactions and returns.
  - [x] Gate at least one transition on collected items to set up later objectives.
  - [x] Ensure the lore guide includes entries for newly introduced locations or key items.
  - [x] Update automated tests so expectations match the broadened content.
  - [x] Update documentation if new commands, items, or mechanics are introduced.
  - [x] Capture notes about additional engine support needed for future iterations.
    - [x] Follow-up: Explore conditional narration hooks (beyond inventory checks) for future scripted-engine enhancements.
      - [x] Define JSON schema and engine support for conditional narration triggers.
      - [x] Update the scripted engine to evaluate the new conditions and record custom events when triggered.
      - [x] Extend the bundled scene data with at least one conditional narration example.
      - [x] Cover the new behaviour with automated tests.
      - [x] Document the data format updates for adventure authors.
  - [x] Flesh out the `starting-area` branches leading to the scavenger camp and lookout tutorials.
  - [x] Author narrative beats for the Sunken Bastion hub scenes.
  - [x] Define the Aether Spire ascent and finale scaffolding.
  - [x] Review lore flavour interactions to highlight journal and memory hooks.
  - [x] Validate the expanded scene data for structural errors and fix any inconsistencies discovered.
    - [x] Correct the malformed `look` transition formatting in the `collapsed-hall` scene.
  - [x] Mark the original checklist item complete once all subtasks pass review.
- [x] Update scripted-engine tests and fixtures to cover the expanded scene graph and any new command patterns.
  - [x] Add regression coverage validating transition targets, required items, and failure messages for gated actions. *(Added targeted tests for the ranger signal gate, flooded archives study requirement, and related success flows.)*
  - [x] Add coverage for the new `journal` and `inventory` command summaries. *(Added tests asserting history truncation and alphabetised inventory listings.)*
- [x] Refresh golden transcripts (if any) so the CLI demo walkthrough exercises the broader storyline. *(Captured an updated CLI walkthrough transcript and regression test to cover the expanded regions.)*
- [x] Document the enhanced demo in `docs/data_driven_scenes.md`, including a high-level map, quest summaries, and authoring tips for further expansion. *(Added an "Expanded Demo Reference" section summarising regions, quest flow, and future authoring guidance.)*

## Priority 10: Browser-Based Scene Editor
- [ ] Design and implement a comprehensive web-based GUI for editing and extending scene data to make adventure authoring accessible to non-programmers.
  - [ ] **Phase 1: Foundation & Backend API**
    - [x] Analyze current JSON schema and identify all data relationships (scenes, transitions, items, conditions). *(Documented the existing runtime model in `docs/web_editor_schema.md` to guide the web editor API design.)*
    - [x] Design RESTful API specification for scene CRUD operations. *(Documented in `docs/web_editor_api_spec.md`.)*
    - [ ] Implement FastAPI backend with the following endpoints:
      - [x] `GET /api/scenes` - List all scenes with metadata *(Implemented read-only endpoint backed by the scripted scene store, including pagination, filtering, and validation summaries.)*
      - [x] `GET /api/scenes/{scene_id}` - Get detailed scene data *(Implemented read-only detail endpoint returning full scene definitions with optional validation metadata.)*
      - [x] `PUT /api/scenes/{scene_id}` - Update existing scene *(Adds optimistic concurrency checks, persistence, and regression tests.)*
      - [x] `POST /api/scenes` - Create new scene *(Adds optimistic concurrency checks, validation summaries, and persistence with regression tests.)*
      - [x] `DELETE /api/scenes/{scene_id}` - Delete scene (with dependency checks) *(Prevents removal when other scenes reference the target and updates dataset version metadata.)*
      - [x] `GET /api/scenes/validate` - Full integrity validation *(Added read-only endpoint returning quality, reachability, and item-flow summaries with test coverage.)*
      - [x] `GET /api/scenes/graph` - Scene connectivity graph data *(returns node/edge metadata with transition details and start-scene selection.)*
      - [x] `POST /api/scenes/import` - Import JSON scene data *(Provides REST-aligned endpoint alongside legacy path.)*
      - [x] `GET /api/scenes/export` - Export current scenes as JSON *(Adds REST-aligned alias mirroring the legacy endpoint.)*
    - [ ] Add comprehensive validation engine:
      - [x] Scene reference integrity (no broken targets) *(Extended analytics and validation to surface transitions pointing to undefined scenes, with updated API reporting.)*
      - [x] Item flow analysis (sources vs requirements)
      - [x] Reachability analysis (unreachable scenes/items) *(Validation now flags unreachable scenes and item dependencies, surfaces warnings in API responses, and exposes summary metadata.)*
      - [x] Circular dependency detection
      - [x] Command uniqueness validation
    - [x] Implement WebSocket endpoint for live adventure testing.
    - [x] Add unit tests covering all API endpoints and validation logic.
      - [x] Added regression coverage for the create/delete endpoints and import/export aliases.
      - [x] Added permission enforcement tests for scene and branch mutations when project collaboration is enabled.
    - [x] Document API specification with OpenAPI/Swagger. *(Documented the FastAPI OpenAPI/Swagger workflow and added tagged metadata so the auto-generated docs surface grouped endpoints.)*

  - [ ] **Phase 2: Core Frontend Architecture**
    - [x] Set up React application with TypeScript for type safety. *(Added `web/scene-editor` package with React + TypeScript scaffolding and type-check script.)*
    - [x] Configure build pipeline (Vite/Webpack) with development server. *(Added a Vite + React toolchain with dev/build/preview scripts and updated TypeScript configuration.)*
    - [x] Implement responsive CSS framework (Tailwind CSS or Material-UI). *(Integrated Tailwind CSS with custom theme tokens, global styles, and utility-driven placeholder layout.)*
    - [ ] Create base component library:
      - [x] Layout components (headers, sidebars, panels) *(Introduced reusable EditorShell, Header, Sidebar, and Panel React components to establish shared layout primitives.)*
      - [x] Form components (inputs, selects, textareas) *(Added shared TextField, SelectField, and TextAreaField components with accessibility helpers and demo usage in the shell.)*
      - [x] Data display components (tables, cards, badges) *(Added Card, Badge, and DataTable primitives with demo usage inside the editor shell to showcase validation summaries.)*
      - [x] Navigation components (breadcrumbs, tabs) *(Implemented shared Breadcrumbs and Tabs primitives with demo usage and interaction logging in the editor prototype.)*
    - [x] Set up state management (Redux Toolkit or Zustand).
    - [x] Implement API client with proper error handling and loading states. *(Added a typed API client wrapper with loading/error tracking in the Zustand store and wired the scene table UI to surface fetch state feedback.)*
    - [x] Add routing system for different editor views. *(Implemented BrowserRouter-driven layout with dedicated overview, library, create, and detail placeholder routes.)*

  - [ ] **Phase 3: Scene List & Basic Editing**
    - [ ] Implement scene list view:
      - [x] Searchable/filterable scene table *(Implemented live search with debounce, validation status filters, and reset controls in the library view.)*
    - [x] Scene metadata display (description preview, choice count, transition count)
    - [x] Quick actions (edit, duplicate, delete) *(Added action buttons that prefill the editor form, prepare duplicates, and surface deletion placeholders with navigation log updates.)*
    - [x] Validation status indicators (errors, warnings) *(Icon-based badges in the scene table and status breakdown now reflect API validation states.)*
  - [ ] Create basic scene editor form:
    - [x] Scene ID and description editing *(Implemented dedicated scene detail page with editable ID/description fields, API-backed save flow, and validation messaging.)*
    - [x] Dynamic choice list editor (add/remove/reorder) *(Added interactive choice list management with validation, reordering controls, and API integration.)*
    - [x] Basic transition editor (target selection, narration) *(Implemented transition editor with target suggestions, narration validation, and save integration.)*
    - [x] Real-time validation feedback *(Inline field errors now update as you type, and saving is blocked until issues are resolved.)*
    - [x] Auto-save functionality *(Scene editor now auto-saves after periods of inactivity when changes are valid, with status feedback.)*
    - [ ] Implement scene creation wizard:
      - [x] Template selection (empty, copy from existing) *(Added interactive wizard step with template cards and duplication flow.)*
      - [x] Guided setup for basic properties *(Wizard now walks through scene ID, type, and summary with validation hints and success messaging.)*
      - [x] Integration with scene list *(Wizard saves drafts into the client-side library, updates navigation logs, and links back to the table view.)*
      - [x] Persist new scene drafts through the API and refresh the library from the server once creation is supported end-to-end *(Wizard now posts new scenes to the FastAPI backend, duplicates full scene data when cloning, and reloads the library from the server.)*
    - [x] Add scene deletion with dependency checking:
      - [x] Show which scenes reference the target *(Scene API now exposes a references endpoint and the library view surfaces referencing scenes before deletion.)*
      - [x] Confirmation dialog with impact analysis
      - [x] Safe deletion that updates references

  - [ ] **Phase 4: Visual Scene Graph**
    - [x] Integrate React Flow library for interactive graph visualization.
      - [x] Add React Flow dependency and expose a dedicated graph route in the editor.
      - [x] Render scene/transition data from the API in React Flow with a basic auto-layout.
      - [x] Surface loading, error, and legend UI so the graph view feels production-ready.
    - [ ] Implement scene node components:
      - [x] Color-coded by type (start, end, branch, linear)
      - [x] Validation status indicators (error, warning, valid) *(Scene graph nodes now include a dedicated status accent and badge pairing for valid, warning, and error states.)*
      - [x] Hover tooltips with scene metadata
      - [x] Click to open editor *(Graph nodes now navigate directly to the scene detail editor when activated, including keyboard support.)*
    - [ ] Implement transition edge components:
      - [x] Different styles for different transition types
      - [x] Conditional edges (requirements) shown differently *(Transitions that require inventory or history now render as dashed blue edges with "requires" labels and legend support.)*
      - [x] Edge labels showing command names *(Graph edges now display stylised command pills with variant indicators and requirements callouts.)*
      - [x] Click to edit transition *(Graph edge labels now navigate to the source scene and focus the corresponding transition editor entry.)*
    - [ ] Add graph interaction features:
      - [x] Drag-and-drop scene positioning *(Added layout editing mode with draggable scene nodes and resettable manual overrides.)*
      - [x] Zoom and pan controls *(Introduced overlay controls for zooming, panning modes, and scroll zoom toggles.)*
      - [ ] Minimap for large graphs
      - [ ] Auto-layout algorithms
      - [ ] Search and focus on specific scenes
    - [ ] Implement dependency highlighting:
      - [ ] Highlight item flow chains
      - [x] Show unreachable scenes in red *(Scene graph nodes, tooltips, minimap, and legend now surface unreachable scenes with distinct red styling.)*
      - [ ] Trace paths between scenes
      - [ ] Critical path analysis

  - [ ] **Phase 5: Advanced Editing Features**
    - [ ] Create comprehensive transition editor:
      - [ ] Target scene dropdown with autocomplete
      - [ ] Rich text editor for narration
        - [ ] Evaluate rich text frameworks that output Markdown-compatible content
        - [x] Document requirements and integration plan *(see `docs/rich_text_editor_plan.md`)*
        - [x] Prototype Markdown rendering in the CLI runtime *(Added ANSI Markdown renderer and wired it into the CLI formatting flow.)*
        - [ ] Integrate the editor into the scene authoring UI shell
        - [ ] Add collaborative enhancements (presence indicators, inline comments)
      - [ ] Item requirements multi-select
      - [ ] Item consumption configuration
      - [ ] Failure narration editor
      - [ ] Conditional logic builder
    - [ ] Implement choice matrix editor:
      - [ ] Grid view of all choices across scenes
      - [ ] Bulk editing capabilities
      - [ ] Command standardization tools
      - [ ] Consistency checking
    - [ ] Build conditional logic visual editor:
      - [ ] Drag-and-drop condition builder
      - [ ] Support for `requires_history_any/all`
      - [ ] Visual representation of complex conditions
      - [ ] Testing interface for conditions
    - [ ] Add item flow analyzer:
      - [ ] Visual item dependency graph
      - [ ] Source tracking (where items come from)
      - [ ] Usage tracking (where items are required)
      - [x] Orphaned item detection *(Implemented analytics helpers and CLI reporting for orphaned/unsourced items.)*
      - [x] Item balance analysis *(Added award/consumption balance classification and reporting.)*

  - [ ] **Phase 6: Live Preview & Testing**
    - [ ] Implement embedded adventure player:
      - [ ] Real-time scene rendering
      - [ ] Interactive choice selection
      - [ ] State tracking (location, inventory, history)
      - [ ] Reset and restart capabilities
    - [ ] Create testing toolkit:
      - [x] State manipulation tools (set inventory, history). *(Introduced `testing_toolkit` helpers for resetting inventory and history with regression tests.)*
      - [x] Jump to specific scenes *(Added `jump_to_scene` helper for quickly moving the world state during tests with optional history recording.)*
      - [x] Debug mode showing internal state *(Introduced `debug_snapshot` helper returning a structured `WorldDebugSnapshot` for assertions.)*
      - [x] Step-by-step execution *(Added `step_through` helper and tests for scripted command execution with memory tracking.)*
    - [ ] Add WebSocket integration for live updates:
      - [ ] Real-time scene updates in preview
      - [ ] Collaborative editing indicators
      - [ ] Change broadcasting
    - [ ] Implement playtesting features:
      - [ ] Session recording and replay
        - [x] Add a playtest session transcript recorder that captures player inputs and resulting events for later review.
        - [x] Expose API/WebSocket commands to download or clear the recorded transcript from an active session. *(Added HTTP transcript endpoints, WebSocket commands, and coverage.)*
        - [ ] Implement a replay helper that can step through recorded playtest transcripts for automated regression testing.
      - [ ] Path tracking and analytics
      - [ ] Playtester feedback collection
      - [x] A/B testing for narrative variants *(Added analytics comparison helpers, reporting formatters, documentation, and regression coverage for variant deltas.)*
        - [x] Provide analytics utilities to compare two scene collections and summarise metric deltas.
        - [x] Add reporting helpers/CLI output for variant comparisons.
        - [x] Document the workflow and cover it with regression tests.

  - [ ] **Phase 7: Import/Export & File Management**
    - [ ] Build robust JSON import system:
      - [x] File upload with validation *(Implemented `/api/import/scenes` to accept JSON uploads, validate structure, and surface reachability/quality reports for the uploaded dataset.)*
      - [x] Schema migration support *(Import endpoint accepts `schema_version` and migrates legacy v1 datasets before validation.)*
      - [x] Conflict resolution (merge vs replace) *(Import validation now reports merge vs replace change plans to highlight updates, additions, and removals.)*
      - [x] Backup creation before import *(Added a `SceneService.create_backup` helper that writes scene snapshots to disk with configurable formatting and returns metadata for operator logs, covered by unit tests and documented in the API spec.)*
    - [ ] Implement export options:
      - [x] Full scene export *(Added `/api/export/scenes` endpoint returning the bundled dataset with timestamps.)*
      - [x] Selective scene export
        - [x] Support filtering `/api/export/scenes` by a comma-separated `ids` query parameter so only matching scenes are included.
      - [x] Document the new selective export behaviour in the API specification.
      - [x] Add regression tests covering filtered exports and error handling.
      - [x] Minified vs pretty-printed JSON
        - [x] Add an API option to request minified or pretty-printed payloads.
        - [x] Ensure the service layer produces the requested formatting.
        - [x] Document the formatting option in the API reference.
        - [x] Add automated tests covering both formatting modes.
      - [x] Backup and versioning *(Export payload now includes deterministic version ids, checksums, and suggested backup filenames.)*
    - [ ] Add version control integration:
      - [x] Git-style change tracking
        - [x] Add API endpoint providing scene dataset diff summaries
        - [x] Document the diff workflow in the API reference
        - [x] Cover diff computation with automated tests
    - [x] Diff visualization *(API now returns HTML diff tables alongside unified diffs with documentation and tests.)*
        - [x] Provide HTML-rendered diff fragments from the API for changed scenes.
        - [x] Document the diff visualisation field in the API specification.
        - [x] Add regression tests covering the HTML diff output.
      - [x] Rollback capabilities *(Added `/api/scenes/rollback` planning endpoint with version metadata, diffs, and replace strategy coverage.)*
      - [x] Branch management for different storylines
        - [x] Add an API branch planning endpoint that surfaces diffs, version metadata, and merge vs replace strategies with tests.
        - [x] Document the branch planning workflow in the API specification.
        - [x] Persist branch definitions and expose listing/creation endpoints.
          - [x] Design a storage format and repository for saved branch definitions.
          - [x] Implement API endpoints to list and create branch definitions backed by the repository.
          - [x] Add automated tests and documentation updates covering the new branch persistence workflow.
        - [x] Provide an API endpoint to retrieve saved branch definitions including metadata, plans, and scenes.
        - [x] Support deleting saved branch definitions via the API with filesystem persistence cleanup.
        - [x] Document the retrieval and deletion workflows and add regression tests.
    - [ ] Create project management features:
    - [ ] Multiple adventure projects
      - [x] Add a filesystem-backed project registry for discovering available adventure datasets.
    - [x] Expose API endpoints for listing and retrieving registered projects.
    - [x] Document the project workflow and cover it with automated tests.
    - [x] Project templates *(Added template catalogue/listing endpoints plus an instantiation workflow that materialises new projects from reusable datasets, with documentation and regression tests.)*
    - [x] Asset organization
      - [x] Add an asset inventory endpoint that enumerates project directories and files with MIME hints and timestamps.
      - [x] Ensure new projects ship with a prepared `assets/` directory and cover the flow with automated tests.
      - [x] Document the asset listing API and response schema for editor tooling.
    - [x] Collaborative permissions
      - [x] Define collaborator roles and metadata persistence.
      - [x] Add API endpoints for managing project collaborators.
      - [x] Cover collaborator workflows with automated tests.

  - [x] **Phase 8: Quality of Life & Polish**
    - [x] Implement comprehensive search:
      - [x] Global text search across all scenes *(Added search utilities and API endpoint for querying scene text with highlighted spans.)*
      - [x] Advanced filters (by type, validation status, etc.) *(Search utilities now support field/scene filters and the API accepts comma-separated field type and validation filters with regression coverage.)*
        - [x] Extend search utilities to support field-type and scene filters
        - [x] Surface field-type filtering in the API/search endpoint
        - [x] Add validation-status filtering support via the API
        - [x] Expand tests covering the new filtering capabilities
      - [x] Search and replace functionality *(Added in-place scene text replacement utilities with automated coverage.)*
      - [x] Reference finding *(Implemented structured reference detection utilities with filtering and regression coverage.)*
        - [x] Define reference categories for scenes, items, and history usage.
        - [x] Implement utilities to locate structured references with optional filters.
        - [x] Add regression tests covering reference detection scenarios.
    - [x] Add keyboard shortcuts and accessibility:
      - [x] Common action shortcuts *(Added CLI single-key shortcuts for quit/help/status/tutorial with documentation and tests.)*
      - [x] Tab navigation *(Added readline-powered tab completion covering system commands, story choices, and editor actions with regression tests and documentation updates.)*
      - [x] Screen reader support *(Added a `--screen-reader` CLI flag that removes ANSI styling, simplifies glyphs, and expands choice descriptions for assistive tech.)*
      - [x] High contrast mode *(Added a `--high-contrast` CLI flag that swaps in a brighter Markdown palette with documentation and tests.)*
    - [x] Create help system:
      - [x] Interactive tutorials *(Added a CLI `tutorial` command with a guided walkthrough covering choices, system commands, and persistence tips.)*
      - [x] Context-sensitive help *(Added a CLI `help` command that surfaces current story choices alongside system command guidance.)*
      - [x] Best practices guide *(Documented adventure design guidance in `docs/best_practices.md` and linked it from the README.)*
      - [x] Troubleshooting documentation *(Added `docs/troubleshooting.md` and linked it from the README troubleshooting section.)*
    - [x] Implement data analytics:
      - [x] Adventure complexity metrics
        - [x] Define core metrics to compute for scripted scene collections.
        - [x] Implement metrics utilities with automated tests.
        - [x] Provide a CLI/report helper for summarising the results.
      - [x] Reachability statistics *(Reachability analysis utilities, CLI reporting, and regression coverage implemented.)*
        - [x] Add analytics helpers to compute reachable and unreachable scenes from a starting location.
        - [x] Surface a formatted reachability report alongside the existing complexity output.
        - [x] Cover the new helpers with automated tests against sample scenes.
      - [x] Content distribution analysis *(Added word/character distribution metrics across scenes, choices, transitions, failure narrations, and conditional overrides with CLI reporting.)*
      - [x] Quality assessment tools
        - [x] Define heuristics for identifying low-quality scene content.
        - [x] Implement quality assessment reporting utilities and CLI output.
        - [x] Cover the new quality checks with automated tests.

  - [x] **Phase 9: Integration & Deployment**
    - [x] Integrate editor with existing CLI workflow:
      - [x] File watching for automatic reloads *(CLI can now load external scene files, watch them for changes, and ships with documentation plus regression tests.)*
        - [x] Allow the CLI to load scripted scenes from an external JSON file so it shares data with the editor API.
        - [x] Implement a lightweight watcher that detects changes to the external scene file and reloads the scripted story engine in-place.
        - [x] Document the workflow and add automated coverage for the reload behaviour.
      - [x] CLI command to launch editor *(Added in-CLI `editor` command with lifecycle controls, host/port configuration flags, and documentation.)*
      - [x] Development mode integration
        - [x] Propagate the CLI scene path to the embedded editor server so both share live datasets during authoring.
        - [x] Support an `--editor-reload` flag to launch the embedded server with uvicorn auto-reload for iterative testing.
    - [x] Create deployment pipeline:
      - [x] Docker containerization *(Added a Dockerfile and README instructions for running the API via Uvicorn in a container.)*
      - [x] Automated container build workflow *(Added a GitHub Actions workflow that builds/pushes container images to GHCR on demand.)*
      - [x] Document release pipeline usage *(Documented workflow triggers, manual runs, and registry requirements.)*
    - [x] Environment configuration *(API now honours environment variables for scene datasets and branch storage with docs and automated tests.)*
    - [x] Production build optimization
      - [x] Static asset management *(Added an asset bundler CLI that produces hashed ZIP archives and manifests for deployment workflows.)*
        - [x] Expose API endpoint to download project asset files for editors.
        - [x] Generate hashed asset bundles and manifests for deployment via a CLI helper.
      - [x] Provide asset upload and deletion endpoints.
        - [x] Outline upload and deletion API contracts and validation rules.
        - [x] Implement asset storage/deletion logic, FastAPI endpoints, and regression tests.
    - [x] Add authentication and user management:
      - [x] User accounts and profiles
        - [x] Define filesystem-backed storage and services for user profiles.
        - [x] Expose `/api/users` endpoints for managing user profiles.
        - [x] Cover the user profile workflow with automated tests.
      - [x] Project sharing and permissions
        - [x] Validate collaborator assignments reference existing user profiles when a user registry is configured.
        - [x] Enrich collaborator listings with user profile display names when available.
        - [x] Enforce collaborator role restrictions when mutating project resources.
      - [x] Collaborative editing features
        - [x] Track active collaboration sessions with TTL persistence.
        - [x] Expose API endpoints to join, heartbeat, list, and leave sessions.
        - [x] Cover the collaboration session workflow with automated tests.
        - [x] Document collaboration session usage for tooling integrators.
      - [x] Access control *(Scene and branch mutations now require authorised collaborators with regression coverage.)*
    - [x] Implement backup and recovery:
      - [x] Automatic backups
        - [x] Add configurable automatic backup directory and retention settings.
        - [x] Persist pre-mutation automatic backups with regression tests.
        - [x] Document the automatic backup workflow and settings for operators.
      - [x] Cloud storage integration *(Automatic backups can now mirror to S3-compatible buckets with configuration, docs, and tests covering the upload path.)*
    - [x] Disaster recovery procedures *(Documented end-to-end recovery runbook covering preparation, rollback validation, and restore execution.)*
      - [x] Data export for migration *(Added project export API returning ZIP archives with scenes, metadata, and assets plus regression tests.)*

  - [x] **Phase 10: Documentation & Community**
  - [x] Create comprehensive user documentation:
      - [x] Getting started guide *(Added `docs/getting_started.md` with step-by-step setup, quality gates, and troubleshooting tips, and linked it from the README.)*
      - [x] Feature reference *(Documented key capabilities in `docs/feature_reference.md` and linked the overview from the README.)*
      - [x] Advanced techniques *(Documented power-user workflows in `docs/advanced_techniques.md` and linked them from the README.)*
      - [x] Troubleshooting guide *(Expanded `docs/troubleshooting.md` with setup checks, tool diagnostics, and cross-references to related documentation.)*
    - [x] Build developer documentation:
      - [x] API reference *(Documented key runtime modules in `docs/api_reference.md`.)*
      - [x] Extension guide *(Documented developer extension patterns in `docs/extension_guide.md` and linked it from the README.)*
      - [x] Contributing guidelines *(Added `docs/contributing.md` outlining the development workflow, quality gates, and review expectations.)*
      - [x] Architecture overview *(Documented the module layout and extension points in `docs/architecture_overview.md`.)*
    - [x] Establish community features:
      - [x] Scene sharing marketplace
        - [x] Define marketplace entry data model and storage interface.
        - [x] Implement a filesystem-backed marketplace store supporting publish/list/listing pagination.
        - [x] Expose FastAPI endpoints for publishing, listing, and retrieving marketplace entries with validation.
        - [x] Cover the marketplace flow with unit and integration tests and document the workflow.
      - [x] Community templates
        - [x] Define a manifest format and storage location for shared templates.
        - [x] Bundle at least one starter template dataset with metadata.
        - [x] Document how contributors can use and extend the templates.
      - [x] Rating and review system
        - [x] Define review storage model and aggregate metadata for marketplace entries.
        - [x] Expose API endpoints for creating and listing marketplace reviews.
        - [x] Add automated tests and documentation updates for the review workflow.
      - [x] Discussion forums
        - [x] Define filesystem-backed forum storage and supporting services.
        - [x] Expose API endpoints for listing threads and creating posts.
        - [x] Document the forum workflows for contributors and users. *(Added
          `docs/forum_workflows.md` and linked it from the README.)*

## Priority 11: CLI Quality-of-Life
- [x] Add a CLI command that can search scripted scene text for a phrase and
      print matching snippets for debugging and content authoring support. *(Added
      a `search-scenes` command that surfaces formatted snippets plus tests.)*

## Priority 12: CLI Discoverability
- [x] Add a CLI command that lists registered LLM providers that can be used as
      secondary agents during the adventure.
  - [x] Show helpful guidance when no providers are registered, including how
        to add custom factories.
  - [x] Update the CLI help output to mention the new command.
  - [x] Cover the new command with automated tests ensuring the formatted
        output matches expectations when providers are available or absent.
