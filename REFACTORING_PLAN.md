# Text Adventure Repository - Comprehensive Refactoring Plan

## Overview

This document provides a phased refactoring strategy to improve the architecture, maintainability, and testability of the text-adventure framework. The plan addresses monolithic code blocks, missing layers, coupling issues, and component organization problems identified in the structure analysis.

---

## PHASE 1: Backend API Layer Decomposition (CRITICAL)

### Current Problem
`src/textadventure/api/app.py` is a monolithic 10,253-line file containing:
- 95 Pydantic model classes
- ~50 route handler functions
- Mixed concerns (routes, validation, resource building, formatting)
- No clear separation of layers

### Proposed New Structure

```
src/textadventure/api/
├── app.py (refactored) - FastAPI creation + top-level route registration
├── __init__.py - Public API exports
├── settings.py - Configuration (existing)
├── backup.py - Backup utilities (existing)
├── models/
│   ├── __init__.py
│   ├── scene.py - Scene-related Pydantic models
│   ├── project.py - Project-related models
│   ├── marketplace.py - Marketplace models
│   ├── forum.py - Forum models
│   ├── collaboration.py - Collaboration/session models
│   ├── common.py - Shared models (Pagination, ValidationStatus, etc.)
│   └── responses.py - Response wrapper models
├── routes/
│   ├── __init__.py
│   ├── scenes.py - Scene CRUD + operations
│   ├── projects.py - Project management
│   ├── marketplace.py - Marketplace endpoints
│   ├── forum.py - Forum endpoints
│   ├── collaboration.py - Real-time collaboration
│   ├── assets.py - Asset management
│   ├── playtest.py - Playtesting/testing
│   └── health.py - Health checks
├── services/
│   ├── __init__.py
│   ├── scene_service.py - Scene business logic
│   ├── project_service.py - Project operations
│   ├── validation_service.py - Validation + quality checks
│   ├── search_service.py - Search operations
│   ├── analytics_service.py - Analytics computation
│   ├── asset_service.py - Asset handling
│   ├── playtest_service.py - Playtest logic
│   └── marketplace_service.py - Marketplace logic
├── dependencies/
│   ├── __init__.py
│   ├── auth.py - Dependency injection for auth
│   ├── database.py - DB session management
│   └── services.py - Service container DI
├── formatters/
│   ├── __init__.py
│   ├── scene_formatter.py - Scene response formatting
│   ├── graph_formatter.py - Graph response formatting
│   ├── validation_formatter.py - Validation response formatting
│   └── common_formatters.py - Shared formatting logic
├── validators/
│   ├── __init__.py
│   ├── scene_validator.py - Scene-specific validation
│   ├── project_validator.py - Project-specific validation
│   └── common_validators.py - Shared validators
└── errors/
    ├── __init__.py
    └── exceptions.py - API-specific exceptions
```

### Phase 1A: Extract Models (~2-3 days)
1. Create `models/` directory
2. Move all Pydantic `BaseModel` classes into appropriate model files
3. Move Enum classes (`ExportFormat`, `CollaboratorRole`, `ImportStrategy`, etc.)
4. Move helper types and type aliases
5. Update imports in app.py
6. Update tests

**Files to create**: 7 files
**Lines to remove from app.py**: ~2,500-3,000

### Phase 1B: Extract Route Handlers (~4-5 days)
1. Create `routes/` directory with modules organized by feature
2. Extract all `@app.get()`, `@app.post()`, `@app.put()`, `@app.delete()` decorated functions
3. Group related routes (scenes.py for scene endpoints, projects.py for project endpoints, etc.)
4. Create route registration function in app.py to mount routers

**Files to create**: 8 files
**Lines to remove from app.py**: ~3,000-4,000

**Key routes to extract**:
- Scenes: List, Get, Create, Update, Delete, Graph, Search, Validate, Export, Import, Diff
- Projects: List, Get, Create, Update, Delete, Collaborators, Assets, Templates
- Marketplace: List, Get, Publish, Reviews, Search
- Forum: List, Create, Post, Search
- Playtest: Record, Replay, Transcript
- Collaboration: Sessions, Updates, Presence

### Phase 1C: Extract Services (~5-7 days)
1. Create `services/` directory
2. Create `SceneService` class extracting scene business logic from routes
3. Create `ProjectService` for project operations
4. Create `ValidationService` consolidating validation logic
5. Create `SearchService` wrapping search functionality
6. Create `AnalyticsService` computing metrics
7. Update routes to use services instead of inline logic

**Files to create**: 8 files
**Benefit**: Easier to test business logic independently, reusability

**Example SceneService interface**:
```python
class SceneService:
    def list_scenes(self, page: int, page_size: int, search: str = None) -> tuple[list, PaginationMetadata]
    def get_scene(self, scene_id: str) -> dict
    def create_scene(self, data: SceneCreateRequest) -> SceneResource
    def update_scene(self, scene_id: str, data: SceneUpdateRequest) -> SceneResource
    def delete_scene(self, scene_id: str) -> None
    def get_scene_graph(self, start_scene: str) -> SceneGraphResponse
    def validate_scenes(self, start_scene: str = None) -> ValidationReport
    # ... etc
```

### Phase 1D: Extract Formatters & Validators (~2-3 days)
1. Create `formatters/` directory for response building
2. Extract resource builders (e.g., `_build_scene_resource()`)
3. Extract validation formatters (convert raw validation to response format)
4. Create `validators/` for validation helper functions
5. Update services/routes to use formatter utilities

**Files to create**: 6 files

### Phase 1E: Dependency Injection (~2-3 days)
1. Create `dependencies.py` with FastAPI dependencies
2. Create service container/factory
3. Update routes to use DI instead of instantiating services
4. Add support for mocking services in tests

**Result after Phase 1**: 
- `api/app.py` reduced from 10,253 lines to ~200-300 lines
- ~15 new focused modules instead of one monolith
- Clear separation: routes → services → domain
- Much easier to test, understand, and modify

---

## PHASE 2: Frontend Page Component Refactoring

### Problem
Large page components (1,500-2,500 lines) mix multiple concerns:
- Data fetching and state management
- Complex business logic
- Rendering logic
- User interaction handling

### Target: Extract into Container + Presentation Pattern

#### Phase 2A: SceneGraphPage (2,547 lines) → 3-4 focused components

**Current structure**: One massive component

**Target structure**:
```
pages/SceneGraphPage.tsx (600-800 lines)
├── Container for data fetching & state management
└── Delegates to components:

components/scene-graph/
├── SceneGraphContainer.tsx (200 lines) - Smart/container
├── SceneGraphView.tsx (300 lines) - Presentational view
├── SceneGraphToolbar.tsx (150 lines) - Controls
├── SceneGraphLegend.tsx (100 lines) - Legend
├── SceneGraphNodeDetail.tsx (200 lines) - Detail panel
└── useSceneGraph.ts (150 lines) - Custom hook for logic
```

**Steps**:
1. Extract `useSceneGraph` custom hook with business logic
2. Create `SceneGraphView` pure component for rendering
3. Create `SceneGraphContainer` coordinating the page
4. Extract `SceneGraphNodeDetail` into separate component
5. Create helper components for toolbar, legend, etc.

#### Phase 2B: SceneDetailsPage (2,145 lines) → 3-4 focused components

**Target structure**:
```
pages/SceneDetailsPage.tsx (600-800 lines)
├── Container for scene loading & editing

components/scene-editor/
├── SceneDetailsContainer.tsx (150 lines) - Smart/container
├── SceneDetailsForm.tsx (400 lines) - Main form
├── SceneDetailsFormField.tsx (300 lines) - Individual fields
├── useSceneEditor.ts (200 lines) - Editor logic hook
└── useAutoSave.ts (100 lines) - Auto-save logic
```

**Steps**:
1. Extract `useSceneEditor` hook for editor state management
2. Extract `useAutoSave` hook for auto-save logic
3. Split form into smaller components by section
4. Create pure `SceneDetailsForm` component
5. Move validation logic into hooks

#### Phase 2C: ChoiceMatrixPage (1,539 lines) → 2-3 components

**Target structure**:
```
pages/ChoiceMatrixPage.tsx (600 lines)

components/choice-matrix/
├── ChoiceMatrixContainer.tsx (200 lines)
├── ChoiceMatrixView.tsx (300 lines)
└── useChoiceMatrix.ts (150 lines)
```

#### Phase 2D: FormField.tsx (1,019 lines) → Separate field components

**Current**: One giant file with all field types

**Target structure**:
```
components/forms/
├── index.ts - Exports all field types
├── FormField.tsx (200 lines) - Base wrapper + shared logic
├── TextField.tsx (100 lines)
├── TextAreaField.tsx (100 lines)
├── SelectField.tsx (120 lines)
├── AutocompleteField.tsx (150 lines)
├── MarkdownField.tsx (150 lines)
├── DateField.tsx (80 lines)
└── useFormField.ts (80 lines) - Shared hook
```

**Result after Phase 2**:
- Page components: 600-800 lines (from 1,500-2,500)
- Clear container/presentational separation
- Reusable custom hooks for state logic
- Much easier to test individual concerns
- Better code reusability

---

## PHASE 3: Frontend State Management Refactoring

### Problem
Zustand stores mix UI state with domain state, making them complex and hard to reason about.

### Current Structure
```
state/
├── sceneEditorStore.ts - Mixes UI + domain state
└── choiceMatrixStore.ts - UI state
```

### Proposed Structure
```
state/
├── domain/
│   ├── sceneStore.ts - Scene data (from API)
│   ├── projectStore.ts - Project data
│   └── collaboratorsStore.ts - Collaborators
├── ui/
│   ├── editorUIStore.ts - UI state (active tabs, panels, etc.)
│   ├── navigationStore.ts - Navigation state
│   └── toastStore.ts - Toast/notification state
├── hooks/
│   ├── useSceneData.ts - Domain data hook
│   ├── useEditorUI.ts - UI state hook
│   └── useCoordination.ts - Coordinate multiple stores
└── index.ts - Exports
```

### Separation Strategy

**Domain Store** (sceneStore.ts):
```typescript
interface SceneStore {
  // Data from API
  scenes: Record<string, SceneResource> | null;
  currentScene: SceneResource | null;
  isLoadingScenes: boolean;
  scenesError: string | null;
  
  // Actions
  loadScenes(): Promise<void>;
  loadScene(id: string): Promise<void>;
  updateScene(id: string, data: SceneUpdateRequest): Promise<void>;
  deleteScene(id: string): Promise<void>;
}
```

**UI Store** (editorUIStore.ts):
```typescript
interface EditorUIStore {
  // UI state only
  activePrimaryTab: PrimaryTabId;
  activeInspectorTab: InspectorTabId;
  isDetailsPanelOpen: boolean;
  selectedNodeId: string | null;
  zoomLevel: number;
  
  // UI actions
  setActivePrimaryTab(tab: PrimaryTabId): void;
  setSelectedNode(id: string | null): void;
  setZoomLevel(level: number): void;
}
```

**Custom Hook** (useSceneData.ts):
```typescript
export const useSceneData = (sceneId: string) => {
  const scene = useSceneStore((state) => state.scenes[sceneId]);
  const loading = useSceneStore((state) => state.isLoading);
  const updateScene = useSceneStore((state) => state.updateScene);
  
  return { scene, loading, updateScene };
};
```

**Result after Phase 3**:
- Clear separation between data and UI state
- Easier to understand and modify stores
- Better testability
- Reduced prop drilling through custom hooks
- Domain data becomes cache layer

---

## PHASE 4: Backend Analytics Module Refactoring (1,565 lines)

### Problem
`analytics.py` is large and mixes multiple analysis types

### Current Analysis Functions
- `compute_adventure_complexity()` - Breadth metrics
- `analyse_item_flow()` - Item dependency analysis
- `compute_scene_reachability()` - Reachability analysis
- `compare_adventure_variants()` - A/B comparison
- `compute_adventure_content_distribution()` - Text metrics
- `assess_adventure_quality()` - Quality assessment
- `detect_item_dependency_cycles()` - Cycle detection

### Proposed Modular Structure
```
textadventure/analytics/
├── __init__.py - Re-export public API
├── base.py - Shared types and protocols
├── complexity_analyzer.py - Complexity metrics
├── item_flow_analyzer.py - Item flow analysis
├── reachability_analyzer.py - Reachability analysis
├── quality_assessor.py - Quality assessment
├── content_analyzer.py - Content distribution
├── variant_analyzer.py - A/B comparison
├── cycle_detector.py - Dependency cycle detection
└── formatters.py - Report formatting functions
```

**Refactoring approach**:
1. Create `analytics/` package
2. Extract each analysis type into its own module
3. Create `AnalysisResult` base type
4. Implement factory/coordinator to run all analyses
5. Keep public API in `__init__.py` (backwards compatible)

**Result**: Same functionality, easier to extend and maintain

---

## PHASE 5: Test Organization Refactoring

### Current Problem
35 test files, some with 2,000+ lines, unclear grouping

### Proposed Structure
```
tests/
├── conftest.py - Shared fixtures
├── unit/
│   ├── __init__.py
│   ├── test_world_state.py
│   ├── test_story_engine.py
│   ├── test_multi_agent.py
│   ├── test_llm.py
│   ├── test_persistence.py
│   └── ... (one per module)
├── integration/
│   ├── __init__.py
│   ├── test_cli.py - CLI integration
│   ├── test_llm_providers.py
│   ├── test_playtest_flow.py
│   └── test_multi_agent_flow.py
├── api/
│   ├── __init__.py
│   ├── conftest_api.py - API-specific fixtures
│   ├── test_scenes_routes.py - Split from monolithic file
│   ├── test_projects_routes.py
│   ├── test_marketplace_routes.py
│   ├── test_forum_routes.py
│   ├── test_collaboration_routes.py
│   └── services/
│       ├── test_scene_service.py
│       ├── test_project_service.py
│       ├── test_validation_service.py
│       └── test_search_service.py
├── fixtures/
│   ├── __init__.py
│   ├── scene_fixtures.py
│   ├── project_fixtures.py
│   └── transcript_fixtures.py
├── utils/
│   ├── __init__.py
│   ├── test_client_builders.py
│   └── assertion_helpers.py
└── data/
    ├── (existing fixture data)
    └── fixtures.json
```

**Migration steps**:
1. Create new directory structure
2. Move unit tests to `unit/`
3. Move integration tests to `integration/`
4. Split large API test files by route module
5. Create API service tests for business logic
6. Extract common fixtures and helpers
7. Update imports

**Result after Phase 5**:
- Tests organized by layer and concern
- Faster test discovery and execution
- Easier to find and run specific test categories
- Reduced cognitive load when writing tests

---

## PHASE 6: Backend Utilities Organization

### Problem
Helper functions scattered throughout codebase

### Proposed Structure
```
textadventure/
├── utils/
│   ├── __init__.py
│   ├── validation.py - Common validation logic
│   ├── serialization.py - Serialization helpers
│   ├── text_processing.py - Text utilities
│   ├── id_generation.py - ID/slug generation
│   ├── pagination.py - Pagination helpers
│   └── imports.py - Dynamic import helpers
└── domain/
    ├── __init__.py
    ├── scene.py - Scene domain model
    ├── project.py - Project domain model
    ├── collaboration.py - Collaboration model
    └── asset.py - Asset model
```

**Current scattered functions to organize**:
- `_slugify_*()` - Move to `utils/id_generation.py`
- `_normalise_*()` - Move to `utils/serialization.py` or `utils/validation.py`
- `_validate_*()` - Move to `utils/validation.py`
- `_compute_*()` - Move to appropriate domain or services
- `_parse_*()` - Move to `utils/serialization.py`
- `_build_*()` - Already moving to formatters (Phase 1D)

---

## PHASE 7: Frontend Component Library & Composition

### Problem
Common patterns repeated, missing abstractions

### Proposed Additions
```
components/
├── dialogs/
│   ├── ConfirmDialog.tsx - Generic confirmation
│   ├── AlertDialog.tsx - Generic alert
│   ├── FormDialog.tsx - Generic form wrapper
│   └── useDialog.ts - Dialog state hook
├── forms/
│   ├── FormSection.tsx - Section wrapper
│   └── FormGrid.tsx - Grid layout for forms
├── tables/
│   ├── BaseTable.tsx - Extracted table logic
│   ├── useTableSort.ts - Sort logic hook
│   ├── useTablePagination.ts - Pagination logic
│   └── useTableSelection.ts - Selection logic
├── editors/
│   ├── ListEditor.tsx - Generic list edit pattern
│   ├── useListEditor.ts - List edit logic
│   └── ItemEditorDialog.tsx - Item edit dialog
├── loaders/
│   ├── LoadingSpinner.tsx
│   ├── SkeletonLoader.tsx
│   └── LoadingState.tsx - Wrapper for states
└── patterns/
    ├── AsyncBoundary.tsx - Error boundary for async
    ├── useAsync.ts - Async operation hook
    └── useAsyncForm.ts - Form + async operations
```

**Goals**:
- Reduce code duplication
- Create reusable patterns
- Improve component consistency
- Make complex patterns easier to implement

---

## PHASE 8: Frontend Custom Hooks Library

### Missing Hooks
```
hooks/
├── api/
│   ├── useSceneList.ts - Fetch scenes with caching
│   ├── useScene.ts - Fetch single scene
│   ├── useSceneUpdate.ts - Handle scene updates
│   └── useSceneDelete.ts - Handle deletion
├── forms/
│   ├── useFormState.ts - Form state management
│   ├── useFormValidation.ts - Validation logic
│   ├── useAutoSave.ts - Auto-save implementation
│   └── useDebounce.ts - Debounce hook
├── ui/
│   ├── useModal.ts - Modal state
│   ├── useToast.ts - Toast notifications
│   ├── useSort.ts - Table sorting
│   └── useSearch.ts - Search with debounce
└── coordination/
    ├── useRouteNavigation.ts - Route sync
    └── useBreadcrumbs.ts - Breadcrumb state
```

**Goals**:
- Encapsulate common patterns
- Make pages/components simpler
- Improve testability of logic
- Enable hook reuse across components

---

## PHASE 9: Documentation Updates

### New Files to Create
1. **ARCHITECTURE.md** - High-level architecture overview (update existing if exists)
2. **API_LAYER_REFACTOR.md** - Guide to new API structure
3. **COMPONENT_PATTERNS.md** - Frontend component best practices
4. **STATE_MANAGEMENT.md** - Zustand store organization guide
5. **TESTING_STRATEGY.md** - Testing guidelines by layer
6. **EXTENSION_POINTS.md** - Where to add new features

### Updates to Existing Docs
- Update README with new structure
- Update CONTRIBUTING.md with refactored guidelines
- Update Agents.md with new organization
- Add inline code documentation for complex modules

---

## IMPLEMENTATION ROADMAP

### Timeline Estimate
Assuming 1-2 developers, part-time:

| Phase | Duration | Priority |
|-------|----------|----------|
| Phase 1A (Extract Models) | 2-3 days | CRITICAL |
| Phase 1B (Extract Routes) | 4-5 days | CRITICAL |
| Phase 1C (Extract Services) | 5-7 days | CRITICAL |
| Phase 1D (Formatters/Validators) | 2-3 days | HIGH |
| Phase 1E (Dependency Injection) | 2-3 days | HIGH |
| **Phase 1 Total** | **15-21 days** | |
| Phase 2 (Frontend Pages) | 8-10 days | CRITICAL |
| Phase 3 (State Management) | 4-5 days | HIGH |
| **Frontend Total** | **12-15 days** | |
| Phase 4 (Analytics) | 3-4 days | MEDIUM |
| Phase 5 (Tests) | 5-7 days | MEDIUM |
| Phase 6 (Utils) | 2-3 days | LOW |
| Phase 7-8 (Components/Hooks) | 8-10 days | MEDIUM |
| Phase 9 (Docs) | 3-4 days | LOW |
| **TOTAL** | **48-68 days** | |

### Recommended Execution Order
1. **Start with Phase 1** (Backend API) - Least disruption to frontend, can be done incrementally
2. **Parallel: Phase 4** (Analytics) - Independent of Phase 1
3. **Then Phase 2-3** (Frontend) - After API is stabilized
4. **Finish with Phase 5-9** (Tests, Utils, Docs)

### Per-Phase Commit Strategy
Each phase should result in:
- Separate feature branch
- Comprehensive test updates
- Documentation updates
- Clean git history with atomic commits

---

## SUCCESS CRITERIA

### After Complete Refactoring

- **Code Quality**:
  - No file > 1,000 lines (except maybe large test files)
  - Max 50 route handlers per file
  - Clear separation of concerns (layers visible)
  - Coupling metrics reduced significantly

- **Maintainability**:
  - New developers can understand structure in <1 hour
  - Adding new API endpoint takes <30 mins
  - Adding new component takes <30 mins
  - Complex bugs easier to trace

- **Testability**:
  - Can test business logic without HTTP layer
  - Can test UI logic without API layer
  - Mock injection straightforward
  - Test execution time reduced

- **Developer Experience**:
  - File organization intuitive
  - IDE code navigation faster
  - Less scroll/search to understand flow
  - Contribution guidelines clear

---

## RISK MITIGATION

1. **Large refactors introduce bugs**
   - Maintain extensive test suite throughout
   - Keep backward compatibility layer during transition
   - Refactor incrementally, not all at once
   - Run integration tests frequently

2. **Breaking changes to API surface**
   - Keep public APIs stable in `__init__.py`
   - Deprecation period for old imports
   - Clear migration guide for internal users

3. **Parallel development conflicts**
   - Suggest doing refactoring in dedicated branches
   - Keep refactoring and feature work separate
   - Frequent rebasing and conflict resolution
   - Clear communication with team

4. **Test failures**
   - Maintain 100% test passage throughout refactoring
   - Create regression tests before refactoring
   - Keep old test data/fixtures
   - Don't delete tests, only move/refactor them

---

## CHECKLIST FOR EACH PHASE

Before starting a phase:
- [ ] Create feature branch
- [ ] Document the plan in a comment/PR description
- [ ] Identify all affected files
- [ ] Plan test updates
- [ ] Estimate effort

During the phase:
- [ ] Make incremental commits (not one giant commit)
- [ ] Update related tests at each step
- [ ] Run full test suite after each commit
- [ ] Update imports/exports
- [ ] Check for dead code to remove

After the phase:
- [ ] All tests pass
- [ ] Update documentation
- [ ] Create PR with clear description
- [ ] Get code review
- [ ] Address feedback
- [ ] Merge to main

---

## FUTURE IMPROVEMENTS (Beyond This Plan)

1. **Migrate to async/await throughout** - More consistent async handling
2. **Add API versioning** - Support multiple API versions
3. **Implement proper DAO/Repository pattern** - For data persistence layer
4. **Add event bus** - For cross-concern communication
5. **Implement CQRS** - If complexity grows further
6. **Add observability** - Logging, tracing, metrics
7. **Frontend: Move to Next.js or similar** - If SSR/SSG needed
8. **Add E2E tests** - Playwright or Cypress
9. **Implement feature flags** - For safer deployments
10. **Add performance monitoring** - Track metrics over time

---

## CONCLUSION

This refactoring plan addresses the main architectural issues while preserving the existing strengths of the codebase. By following this plan phased approach, the team can significantly improve maintainability and developer experience without a complete rewrite.

The estimated total effort (48-68 days) for a mid-size project like this is reasonable and should yield substantial long-term productivity gains.
