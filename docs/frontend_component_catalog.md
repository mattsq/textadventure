# Frontend Component Catalog

This catalog summarises the reusable React primitives that power the scene editor UI. Use it as a reference when composing new screens, extending feature areas, or standardising styling and behaviour across the app.

## How to read this guide

- **Domain sections** organise components by their folders in `web/scene-editor/src/components/`.
- **Key props** highlight the contract you should honour when instantiating a component. Optional props are omitted unless they unlock notable behaviour.
- **Usage notes** call out accessibility affordances, styling nuances, and integration tips so you can stay consistent with the existing experience.

## Cross-cutting patterns

- All components lean on Tailwind utility classes and share helper `classNames` functions to concatenate conditional classes. Keep new variants aligned with the tone and spacing set here.【F:web/scene-editor/src/components/display/Card.tsx†L6-L43】【F:web/scene-editor/src/components/navigation/Tabs.tsx†L1-L50】
- Inputs surfaced through `FormField` variants automatically wire accessible labelling, `aria-describedby`, and error messaging. Reuse these wrappers to avoid duplicating accessibility plumbing.【F:web/scene-editor/src/components/forms/FormField.tsx†L12-L109】
- Validation badges and graph elements reuse `ValidationState` descriptors from the Zustand store. Import `VALIDATION_STATUS_DESCRIPTORS` when you need aligned copy or badge variants for new surfaces.【F:web/scene-editor/src/components/display/ValidationStatusIndicator.tsx†L1-L78】

## Layout primitives

| Component | Location | Key props | Usage notes |
| --- | --- | --- | --- |
| `EditorShell` | `layout/EditorShell.tsx` | `header`, `sidebar`, `children`, `footer` | Wraps entire editor pages with optional sidebar rail and footer. The sidebar slot renders inside a fixed-width panel with scroll; omit it for full-width canvases.【F:web/scene-editor/src/components/layout/EditorShell.tsx†L4-L35】 |
| `EditorHeader` | `layout/EditorHeader.tsx` | `title`, `subtitle`, `badge`, `actions` | Provides consistent hero header styling with gradient background and responsive stacking. Pass small React nodes to `badge` for status pills and supply action buttons for top-right controls.【F:web/scene-editor/src/components/layout/EditorHeader.tsx†L4-L35】 |
| `EditorPanel` | `layout/EditorPanel.tsx` | `title`, `description`, `actions`, `footer`, `variant` | Default variant suits primary content; the `subtle` variant is lighter for nested sections. Use the `footer` slot for helper copy or secondary actions.【F:web/scene-editor/src/components/layout/EditorPanel.tsx†L4-L39】 |
| `EditorSidebar` | `layout/EditorSidebar.tsx` | `title`, `actions`, `sections`, `footer`, `children` | Renders stacked sidebar cards, each with title, content, and optional footer. Pass `sections` for declarative configuration or use `children` for custom layouts.【F:web/scene-editor/src/components/layout/EditorSidebar.tsx†L4-L39】 |

## Display components

| Component | Location | Key props | Usage notes |
| --- | --- | --- | --- |
| `Card` | `display/Card.tsx` | `variant`, `title`, `description`, `icon`, `actions`, `footer`, `compact` | Base surface for grouped content. Hover states and rounded corners match the rest of the editor. `compact` tightens padding for dense data cards.【F:web/scene-editor/src/components/display/Card.tsx†L8-L54】 |
| `Badge` | `display/Badge.tsx` | `variant`, `size`, `leadingIcon`, `trailingIcon` | Semantic badge variants (neutral, info, success, warning, danger) already map to the Tailwind palette. Icons render inside visually hidden spans for screen reader silence.【F:web/scene-editor/src/components/display/Badge.tsx†L8-L50】 |
| `DataTable` | `display/DataTable.tsx` | `columns`, `data`, `caption`, `emptyState`, `onRowClick`, `dense` | Generic table with optional captions, hover rows, and dense spacing toggle. Define `render` functions in columns for bespoke cell formatting.【F:web/scene-editor/src/components/display/DataTable.tsx†L9-L99】 |
| `SceneMetadataCell` | `display/SceneMetadataCell.tsx` | `id`, `description`, `choiceCount`, `transitionCount` | Normalises empty descriptions and renders choice/transition chips with consistent styling for dashboard tables.【F:web/scene-editor/src/components/display/SceneMetadataCell.tsx†L1-L43】 |
| `ValidationStatusIndicator` | `display/ValidationStatusIndicator.tsx` | `status`, `hideLabel`, Badge props | Wraps a `Badge` with iconography and status copy for validation states. Use `hideLabel` when the label duplicates nearby text but keep the SR-only span for accessibility.【F:web/scene-editor/src/components/display/ValidationStatusIndicator.tsx†L55-L94】 |

## Form controls

`FormField.tsx` exports a suite of inputs that share consistent labelling, error display, and focus treatment. Prefer these over raw HTML elements.

| Component | Key props | Usage notes |
| --- | --- | --- |
| `TextField` / `TextAreaField` | `label`, `description`, `error`, `required`, standard input props | Injects `aria` attributes and error text automatically. `TextAreaField` adds min-height styling suited for narrative copy blocks.【F:web/scene-editor/src/components/forms/FormField.tsx†L60-L151】【F:web/scene-editor/src/components/forms/FormField.tsx†L640-L709】 |
| `SelectField` | `options`, `value`, `onValueChange`, `emptyMessage` | Renders a styled `<select>` with error-aware focus rings. Useful for short enumerations that do not warrant autocomplete.【F:web/scene-editor/src/components/forms/FormField.tsx†L710-L799】 |
| `AutocompleteField` | `options`, `value`, `onValueChange`, `emptyMessage` | Keyboard-accessible combobox with filtering and highlight management. Automatically reopens the listbox on focus to encourage discovery of existing scene IDs or items.【F:web/scene-editor/src/components/forms/FormField.tsx†L110-L299】 |
| `MultiSelectField` | `values`, `onChange`, `options`, `placeholder` | Token-based multiselect that deduplicates entries, allows free-form additions, and exposes pill removal buttons. Focus/keyboard behaviour mirrors the autocomplete field for consistency.【F:web/scene-editor/src/components/forms/FormField.tsx†L400-L562】 |
| `MarkdownEditorField` | `value`, `onChange`, `previewMode`, `minHeight` | Wraps `@uiw/react-md-editor` with the same FieldWrapper so markdown narration shares the editor’s accessible labelling and error states.【F:web/scene-editor/src/components/forms/FormField.tsx†L800-L980】 |
| `FormField` | `TextField`, `TextAreaField`, etc. | Factory returning the core primitives, enabling dependency injection in tests. Import when you need to pass component references rather than JSX elements.【F:web/scene-editor/src/components/forms/FormField.tsx†L982-L1044】 |

## Navigation & status affordances

| Component | Location | Key props | Usage notes |
| --- | --- | --- | --- |
| `Breadcrumbs` | `navigation/Breadcrumbs.tsx` | `items`, `separator`, `ariaLabel` | Builds accessible breadcrumb navigation with automatic `aria-current`. Items support links, buttons, or plain spans depending on interaction needs.【F:web/scene-editor/src/components/navigation/Breadcrumbs.tsx†L8-L84】 |
| `Tabs` | `navigation/Tabs.tsx` | `items`, `activeTab`, `onTabChange`, `variant`, `size`, `fullWidth` | Two visual styles (`underline` and `pill`) share keyboard handling and optional badges. Supply `ariaLabel` when the tab context isn’t obvious from surrounding headings.【F:web/scene-editor/src/components/navigation/Tabs.tsx†L8-L117】 |
| `ValidationStatusIndicator` | See display section | — | Often embedded next to breadcrumbs or tabs to surface schema health inline with navigation controls.【F:web/scene-editor/src/components/display/ValidationStatusIndicator.tsx†L55-L94】 |

## Graph canvas components

| Component | Location | Key props | Usage notes |
| --- | --- | --- | --- |
| `SceneGraphNode` | `graph/SceneGraphNode.tsx` | `data.variant`, `data.validationStatus`, `data.onOpen` | React Flow node renderer for scene and terminal nodes. Applies accent rings for scene types, dimming for filtered states, and wires keyboard/ARIA interactions for opening scenes.【F:web/scene-editor/src/components/graph/SceneGraphNode.tsx†L1-L113】 |
| `SceneGraphEdge` | `graph/SceneGraphEdge.tsx` | `data.variant`, `data.hasRequirements`, `data.onOpen` | Custom edge with labelled badges for requirements, consumables, and overrides. `variant` controls accent colour while `onOpen` enables click-to-focus interactions in the side panel.【F:web/scene-editor/src/components/graph/SceneGraphEdge.tsx†L1-L77】【F:web/scene-editor/src/components/graph/SceneGraphEdge.tsx†L78-L140】 |

## Scene authoring workflows

| Component | Location | Key props | Usage notes |
| --- | --- | --- | --- |
| `ChoiceListEditor` | `scene-editor/ChoiceListEditor.tsx` | `choices`, `errors`, `onAddChoice`, `onChange`, `onMoveChoice` | Manages per-choice inputs with move/remove controls and inline validation. Use alongside the store’s choice actions to keep ordering updates immutable.【F:web/scene-editor/src/components/scene-editor/ChoiceListEditor.tsx†L9-L126】 |
| `TransitionListEditor` | `scene-editor/TransitionListEditor.tsx` | `choices`, `transitions`, `targetOptions`, `itemOptions`, handlers | Couples choices to destinations, narration, and inventory rules via composable form fields. Highlights an active choice when synchronising with the graph selection state.【F:web/scene-editor/src/components/scene-editor/TransitionListEditor.tsx†L1-L126】 |
| `SceneDeletionDialog` | `scene-editor/SceneDeletionDialog.tsx` | `state.status`, `state.references`, `onConfirm`, `onCancel` | Presents dependency analysis and confirmation states when removing scenes. Pulls reference tables through `DataTable` to stay visually aligned with other list views.【F:web/scene-editor/src/components/scene-editor/SceneDeletionDialog.tsx†L1-L126】 |

## Collaboration & presence

| Component | Location | Key props | Usage notes |
| --- | --- | --- | --- |
| `CollaboratorPresenceIndicator` | `collaboration/CollaboratorPresenceIndicator.tsx` | Polling interval constants, derived state setters, `Badge` integration | Polls the backend for active sessions, renders presence badges by role, and formats relative timestamps plus scene focus context. Surface it in headers or panels to show who else is editing the project.【F:web/scene-editor/src/components/collaboration/CollaboratorPresenceIndicator.tsx†L5-L104】【F:web/scene-editor/src/components/collaboration/CollaboratorPresenceIndicator.tsx†L131-L214】 |

## When to extend the catalog

- Introduce new primitives when multiple features would benefit from shared markup or behaviour.
- Update this document whenever you add, rename, or materially change a component so onboarding remains smooth.
- Capture domain-specific rules in a nested `AGENTS.md` beside the component code when behaviour cannot be conveyed succinctly here.
