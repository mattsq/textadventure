import React from "react";
import { createSceneEditorApiClient } from "../api";
import { EditorPanel } from "../components/layout";
import {
  Badge,
  Card,
  DataTable,
  SceneMetadataCell,
  ValidationStatusIndicator,
  VALIDATION_STATUS_DESCRIPTORS,
  type DataTableColumn,
} from "../components/display";
import { SelectField, TextAreaField, TextField } from "../components/forms";
import { Breadcrumbs, Tabs, type BreadcrumbItem, type TabItem } from "../components/navigation";
import {
  INSPECTOR_TAB_IDS,
  PRIMARY_TAB_IDS,
  type InspectorTabId,
  type PrimaryTabId,
  type SceneTableRow,
  type SceneTableValidationFilter,
  type ValidationState,
  useSceneEditorStore,
} from "../state";

const validationFilterLabels: Record<SceneTableValidationFilter, string> = {
  all: "All statuses",
  valid: VALIDATION_STATUS_DESCRIPTORS.valid.label,
  warnings: VALIDATION_STATUS_DESCRIPTORS.warnings.label,
  errors: VALIDATION_STATUS_DESCRIPTORS.errors.label,
};

const validationFilterOptions: readonly SceneTableValidationFilter[] = [
  "all",
  "valid",
  "warnings",
  "errors",
];

const formatTimestamp = (value: string): string => {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString();
};

const formatSceneCountLabel = (count: number): string =>
  `${count} ${count === 1 ? "scene" : "scenes"}`;

const sceneTableColumns: DataTableColumn<SceneTableRow>[] = [
  {
    id: "scene",
    header: "Scene",
    className: "align-top",
    render: (row) => (
      <SceneMetadataCell
        id={row.id}
        description={row.description}
        choiceCount={row.choiceCount}
        transitionCount={row.transitionCount}
      />
    ),
  },
  {
    id: "terminal",
    header: "Terminal",
    align: "center",
    render: (row) => (
      <Badge variant={row.hasTerminalTransition ? "info" : "neutral"} size="sm">
        {row.hasTerminalTransition ? "Yes" : "No"}
      </Badge>
    ),
  },
  {
    id: "validation",
    header: "Validation",
    align: "center",
    render: (row) => (
      <ValidationStatusIndicator status={row.validationStatus} />
    ),
  },
  {
    id: "lastUpdated",
    header: "Last Updated",
    align: "right",
    render: (row) => (
      <span className="font-mono text-xs text-slate-300">{formatTimestamp(row.updatedAt)}</span>
    ),
  },
];

export const SceneLibraryPage: React.FC = () => {
  const apiClient = React.useMemo(
    () =>
      createSceneEditorApiClient({
        baseUrl:
          typeof import.meta.env.VITE_SCENE_API_BASE_URL === "string" &&
          import.meta.env.VITE_SCENE_API_BASE_URL.trim() !== ""
            ? import.meta.env.VITE_SCENE_API_BASE_URL
            : undefined,
      }),
    [],
  );

  const primaryTabLogMessages: Record<PrimaryTabId, string> = {
    details: "Primary navigation focused on scene metadata and narrative notes.",
    choices: "Primary navigation focused on branching choice authoring workflows.",
    testing: "Primary navigation focused on the upcoming playtesting harness.",
  };

  const inspectorTabLogMessages: Record<InspectorTabId, string> = {
    overview: "Inspector ready to summarise the active scene at a glance.",
    validation: "Inspector prepared to surface validation alerts that require attention.",
    activity: "Inspector highlighting collaborator activity and version history.",
  };

  const {
    sceneId,
    sceneType,
    sceneSummary,
    statusMessage,
    navigationLog,
    activePrimaryTab,
    activeInspectorTab,
    sceneTableState,
    sceneTableQuery,
    sceneTableValidationFilter,
    loadSceneTable,
    setSceneId,
    setSceneType,
    setSceneSummary,
    setStatusMessage,
    setNavigationLog,
    setActivePrimaryTab,
    setActiveInspectorTab,
    setSceneTableQuery,
    setSceneTableValidationFilter,
  } = useSceneEditorStore();

  const [debouncedSearchQuery, setDebouncedSearchQuery] = React.useState(
    sceneTableQuery,
  );

  React.useEffect(() => {
    const handle = setTimeout(() => {
      setDebouncedSearchQuery(sceneTableQuery);
    }, 300);

    return () => {
      clearTimeout(handle);
    };
  }, [sceneTableQuery]);

  React.useEffect(() => {
    const abortController = new AbortController();
    void loadSceneTable(apiClient, {
      signal: abortController.signal,
      search: debouncedSearchQuery.trim() || undefined,
    });

    return () => {
      abortController.abort();
    };
  }, [apiClient, debouncedSearchQuery, loadSceneTable]);

  const sceneTableRows = sceneTableState.data ?? [];
  const normalizedSearchQuery = sceneTableQuery.trim().toLowerCase();
  const filteredSceneTableRows = React.useMemo<SceneTableRow[]>(
    () =>
      sceneTableRows.filter((row) => {
        const matchesValidation =
          sceneTableValidationFilter === "all" ||
          row.validationStatus === sceneTableValidationFilter;
        if (!matchesValidation) {
          return false;
        }

        if (!normalizedSearchQuery) {
          return true;
        }

        return (
          row.id.toLowerCase().includes(normalizedSearchQuery) ||
          row.description.toLowerCase().includes(normalizedSearchQuery)
        );
      }),
    [normalizedSearchQuery, sceneTableRows, sceneTableValidationFilter],
  );
  const sceneTableError = sceneTableState.error;
  const isSceneTableLoading = sceneTableState.status === "loading";
  const sceneTableLastSyncedAt = sceneTableState.lastUpdatedAt;
  const totalFetchedScenes = sceneTableRows.length;
  const visibleSceneCount = filteredSceneTableRows.length;
  const validationCounts = React.useMemo<
    Record<SceneTableValidationFilter, number>
  >(
    () => {
      const counts: Record<SceneTableValidationFilter, number> = {
        all: sceneTableRows.length,
        valid: 0,
        warnings: 0,
        errors: 0,
      };

      for (const row of sceneTableRows) {
        counts[row.validationStatus] += 1;
      }

      return counts;
    },
    [sceneTableRows],
  );
  const hasActiveQuery = normalizedSearchQuery.length > 0;
  const hasActiveFilters =
    hasActiveQuery || sceneTableValidationFilter !== "all";
  const sceneTableEmptyState = isSceneTableLoading
    ? "Loading scenes…"
    : hasActiveFilters
      ? "No scenes match your filters yet. Try adjusting the search or status filter."
      : "No scenes available yet. Create a scene to get started.";

  const handleSceneTableQueryChange = (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
    setSceneTableQuery(event.target.value);
  };

  const handleSceneTableValidationFilterChange = (
    event: React.ChangeEvent<HTMLSelectElement>,
  ) => {
    setSceneTableValidationFilter(
      event.target.value as SceneTableValidationFilter,
    );
  };

  const handleResetSceneTableFilters = () => {
    if (!hasActiveFilters) {
      return;
    }

    setSceneTableQuery("");
    setSceneTableValidationFilter("all");
    setDebouncedSearchQuery("");
  };

  const breadcrumbItems = React.useMemo<BreadcrumbItem[]>(
    () => [
      {
        id: "workspace",
        label: "Workspace",
        onClick: () =>
          setNavigationLog(
            "Workspace navigation will list available adventures once routing is enabled.",
          ),
      },
      {
        id: "project",
        label: "Demo Adventure",
        onClick: () =>
          setNavigationLog(
            "Project dashboards will surface validation summaries and collaborator activity.",
          ),
      },
      { id: "scene-editor", label: "Scene Editor", current: true },
    ],
    [setNavigationLog],
  );

  const sceneTabs = React.useMemo<TabItem[]>(
    () => [
      {
        id: "details",
        label: "Details",
        description: "Scene metadata overview",
      },
      {
        id: "choices",
        label: "Choices",
        description: "Branching options planner",
      },
      {
        id: "testing",
        label: "Playtesting",
        description: "Live preview harness",
        badge: (
          <span className="rounded-full border border-amber-500/50 bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-200">
            Planned
          </span>
        ),
      },
    ],
    [],
  );

  const inspectorTabs = React.useMemo<TabItem[]>(
    () => [
      { id: "overview", label: "Overview" },
      {
        id: "validation",
        label: "Validation",
        badge: (
          <Badge size="sm" variant="warning">
            Alerts
          </Badge>
        ),
      },
      { id: "activity", label: "Activity" },
    ],
    [],
  );

  const primaryTabContent = React.useMemo<Record<PrimaryTabId, React.ReactNode>>(
    () => ({
      details: (
        <div className="space-y-2">
          <p>
            Scene metadata panels will combine structured fields with context about entry points, tags, and
            author notes so collaborators can understand the purpose of each location at a glance.
          </p>
          <p className="text-slate-300">
            Upcoming iterations will introduce inline validation summaries and change tracking so editors can
            spot regressions without leaving the page.
          </p>
        </div>
      ),
      choices: (
        <div className="space-y-2">
          <p>
            The choice workspace will provide drag-and-drop ordering, quick duplication tools, and consistency
            hints that flag missing failure narration or duplicate commands.
          </p>
          <ul className="list-disc space-y-1 pl-6 text-xs text-slate-300 md:text-sm">
            <li>Preview downstream transitions and their validation status.</li>
            <li>Surface item requirements alongside rewards for balancing.</li>
            <li>Integrate analytics callouts from the validation engine.</li>
          </ul>
        </div>
      ),
      testing: (
        <div className="space-y-2">
          <p>
            Live playtesting inside the editor will stream scripted walkthroughs, allowing authors to iterate
            without swapping back to the CLI runtime.
          </p>
          <p className="text-slate-300">
            The harness will reuse the existing transcript recorder and expose quick-reset controls for
            inventory, history, and branching paths.
          </p>
        </div>
      ),
    }),
    [],
  );

  const inspectorTabContent = React.useMemo<
    Record<InspectorTabId, React.ReactNode>
  >(
    () => ({
      overview: (
        <div className="space-y-1 text-xs text-slate-300 md:text-sm">
          <p>
            Compact summaries will highlight scene health, validation status, and collaboration notes.
          </p>
          <p>
            Use this pane as a quick reference while editing without leaving the form you are working in.
          </p>
        </div>
      ),
      validation: (
        <ul className="list-disc space-y-1 pl-5 text-xs text-amber-200 md:text-sm">
          <li>Pending quality warnings generated by the validation service.</li>
          <li>Reachability issues that require new transitions or endings.</li>
          <li>Item flow mismatches detected by analytics helpers.</li>
        </ul>
      ),
      activity: (
        <div className="space-y-1 text-xs text-slate-300 md:text-sm">
          <p>
            Collaboration history will display recent edits, comments, and review requests.
          </p>
          <p>Tap into automatic backups or branch snapshots to jump back to a prior state.</p>
        </div>
      ),
    }),
    [],
  );

  const isPrimaryTabId = (value: string): value is PrimaryTabId =>
    (PRIMARY_TAB_IDS as readonly string[]).includes(value);
  const isInspectorTabId = (value: string): value is InspectorTabId =>
    (INSPECTOR_TAB_IDS as readonly string[]).includes(value);

  const handlePrimaryTabChange = (tabId: string) => {
    if (!isPrimaryTabId(tabId)) {
      return;
    }
    setActivePrimaryTab(tabId, primaryTabLogMessages[tabId]);
  };

  const handleInspectorTabChange = (tabId: string) => {
    if (!isInspectorTabId(tabId)) {
      return;
    }
    setActiveInspectorTab(tabId, inspectorTabLogMessages[tabId]);
  };

  const sceneIdError = sceneId.trim()
    ? undefined
    : "Scene ID is required to save a draft.";

  const statusMessageClassName = statusMessage
    ? sceneTableState.status === "error"
      ? "text-xs font-medium text-rose-400"
      : "text-xs font-medium text-emerald-400"
    : "text-xs text-slate-400";

  const handleFormSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (sceneIdError) {
      setStatusMessage(null);
      return;
    }
    setStatusMessage(`Draft saved for ${sceneId.trim()}.`);
  };

  return (
    <>
      <EditorPanel
        title="Getting Started"
        description={
          <>
            These layout primitives provide consistent styling for upcoming editor views. Compose them
            to create dashboards, forms, and navigation that match the design system without duplicating
            utility classes in every screen.
          </>
        }
      >
        <p>
          Use the <code className="rounded bg-slate-900 px-1 py-0.5 text-xs">EditorShell</code> to frame pages with optional
          sidebars and shared headers. Drop <code className="rounded bg-slate-900 px-1 py-0.5 text-xs">EditorPanel</code>
          components inside the shell for consistent content blocks, and use <code className="rounded bg-slate-900 px-1 py-0.5 text-xs">EditorSidebar</code>
          to populate navigation, summaries, or contextual helpers.
        </p>
        <p>
          Future tasks will introduce data fetching, routing, and interactive scene editing experiences that leverage these
          foundational components.
        </p>
      </EditorPanel>

      <EditorPanel
        title="Component Showcase"
        variant="subtle"
        description="Quick tips for extending the component set as new editor surfaces come online."
      >
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <Card
            compact
            title="Form primitives"
            description="Input components provide consistent states, helper text, and validation messaging."
            actions={<Badge size="sm">Stable</Badge>}
          >
            <p className="text-slate-300">
              Reuse <code>TextField</code>, <code>SelectField</code>, and <code>TextAreaField</code> for upcoming editor flows
              to minimise duplicated Tailwind classes.
            </p>
          </Card>
          <Card
            compact
            title="Layout shells"
            description="Compose panels, shells, and sidebars to build new views quickly."
            actions={<Badge size="sm">Stable</Badge>}
          >
            <p className="text-slate-300">
              Combine <code>EditorShell</code>, <code>EditorPanel</code>, and <code>EditorSidebar</code> to create dashboards
              for scenes, analytics, or collaborative tools.
            </p>
          </Card>
          <Card
            compact
            title="Display components"
            description="Cards, badges, and tables showcase scene metadata with consistent styling."
            actions={<Badge variant="info" size="sm">New</Badge>}
          >
            <p className="text-slate-300">
              Adopt the new <code>Card</code>, <code>Badge</code>, and <code>DataTable</code> primitives as building blocks for
              dashboards and validation summaries.
            </p>
          </Card>
          <Card
            compact
            title="Document patterns"
            description="Keep usage guidelines current as primitives evolve."
            actions={<Badge variant="warning" size="sm">Todo</Badge>}
          >
            <p className="text-slate-300">
              Update the design system docs with examples, variant guidance, and theming tokens as additional UI is added.
            </p>
          </Card>
        </div>
      </EditorPanel>

      <EditorPanel
        title="Navigation Components"
        description="Breadcrumbs and tabs establish orientation and view-level navigation for the editor."
      >
        <div className="flex flex-col gap-5">
          <div className="flex flex-col gap-2">
            <Breadcrumbs
              items={breadcrumbItems}
              ariaLabel="Editor breadcrumb trail"
              className="text-sm text-slate-300"
            />
            <span className="text-xs text-slate-400 md:text-sm">{navigationLog}</span>
          </div>
          <Tabs
            items={sceneTabs}
            activeTab={activePrimaryTab}
            onTabChange={handlePrimaryTabChange}
            ariaLabel="Primary scene editor views"
          />
          <div className="rounded-xl border border-slate-800/60 bg-slate-900/50 p-4 text-sm text-slate-200 md:text-base">
            {primaryTabContent[activePrimaryTab]}
          </div>
          <Tabs
            items={inspectorTabs}
            activeTab={activeInspectorTab}
            onTabChange={handleInspectorTabChange}
            variant="pill"
            size="sm"
            fullWidth
            ariaLabel="Inspector panels"
          />
          <div className="rounded-xl border border-slate-800/60 bg-slate-900/40 p-4 text-xs text-slate-300 md:text-sm">
            {inspectorTabContent[activeInspectorTab]}
          </div>
        </div>
      </EditorPanel>

      <EditorPanel
        title="Form Component Demo"
        description="Base input components provide consistent styling, validation states, and helper text markup."
      >
        <form className="grid gap-6 md:grid-cols-2" onSubmit={handleFormSubmit}>
          <TextField
            className="md:col-span-1"
            label="Scene ID"
            value={sceneId}
            onChange={(event) => setSceneId(event.target.value)}
            description="Unique identifier used when referencing this scene in transitions and analytics."
            placeholder="enter-scene-id"
            error={sceneIdError}
            required
          />
          <SelectField
            className="md:col-span-1"
            label="Scene Type"
            value={sceneType}
            onChange={(event) => setSceneType(event.target.value)}
            description="Categorise scenes to drive editor filtering and analytics."
          >
            <option value="branch">Branching encounter</option>
            <option value="linear">Linear narration</option>
            <option value="terminal">Ending</option>
            <option value="puzzle">Puzzle / gated progress</option>
          </SelectField>
          <TextAreaField
            className="md:col-span-2"
            label="Scene Summary"
            value={sceneSummary}
            onChange={(event) => setSceneSummary(event.target.value)}
            description="Provide a short synopsis to help collaborators identify the scene at a glance."
            placeholder="Describe the key beats players should expect when they reach this scene."
            rows={5}
          />
          <div className="flex flex-col gap-3 md:col-span-2 md:flex-row md:items-center md:justify-between">
            <span className={statusMessageClassName}>
              {statusMessage ?? "Validation happens live as values change. Submit to simulate a draft save."}
            </span>
            <button
              type="submit"
              className="inline-flex items-center justify-center rounded-lg border border-indigo-400/60 bg-indigo-500/30 px-4 py-2 text-sm font-semibold text-indigo-100 transition hover:bg-indigo-500/40 disabled:cursor-not-allowed disabled:border-slate-700 disabled:bg-slate-800/60 disabled:text-slate-500"
              disabled={Boolean(sceneIdError)}
            >
              Save Draft
            </button>
          </div>
        </form>
      </EditorPanel>

      <EditorPanel
        title="Data Display Components"
        description="Scene summaries, validation states, and statistics can be presented with shared primitives."
      >
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="lg:col-span-2 space-y-3">
            <div className="space-y-3 rounded-lg border border-slate-800/80 bg-slate-900/40 p-4">
              <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_220px]">
                <TextField
                  label="Search scenes"
                  value={sceneTableQuery}
                  onChange={handleSceneTableQueryChange}
                  placeholder="Search by ID or description"
                  description="Filter the table in real time while new results load from the API."
                />
                <SelectField
                  label="Validation status"
                  value={sceneTableValidationFilter}
                  onChange={handleSceneTableValidationFilterChange}
                  description="Limit the table to scenes with a specific validation outcome."
                >
                  {validationFilterOptions.map((option) => (
                    <option key={option} value={option}>
                      {validationFilterLabels[option]} ({validationCounts[option]})
                    </option>
                  ))}
                </SelectField>
              </div>
              <div className="flex flex-col gap-2 pt-1 text-xs text-slate-400 md:flex-row md:items-center md:justify-between md:text-sm">
                <span>
                  Showing <span className="font-semibold text-slate-200">{visibleSceneCount}</span> of{" "}
                  <span className="font-semibold text-slate-200">{totalFetchedScenes}</span> scenes
                  {hasActiveFilters ? " after filters." : "."}
                </span>
                <button
                  type="button"
                  onClick={handleResetSceneTableFilters}
                  className="inline-flex items-center justify-center rounded-lg border border-slate-700/70 bg-slate-900/60 px-3 py-1.5 font-semibold text-slate-200 transition hover:border-slate-500/80 hover:bg-slate-900/80 disabled:cursor-not-allowed disabled:border-slate-800 disabled:text-slate-500"
                  disabled={!hasActiveFilters}
                >
                  Reset filters
                </button>
              </div>
            </div>
            {isSceneTableLoading ? (
              <div className="rounded-lg border border-slate-800/80 bg-slate-900/40 px-4 py-3 text-sm text-slate-300">
                Loading scenes from the API…
              </div>
            ) : null}
            <DataTable
              columns={sceneTableColumns}
              data={filteredSceneTableRows}
              emptyState={sceneTableEmptyState}
              caption={
                <div className="flex flex-col gap-1">
                  <span>Scene dataset loaded from the API with validation coverage.</span>
                  <span className="text-xs text-slate-400">
                    Showing {visibleSceneCount} of {totalFetchedScenes} scenes
                    {hasActiveFilters ? " matching your filters." : "."}
                  </span>
                </div>
              }
            />
            {sceneTableError ? (
              <p className="text-sm text-rose-300">{sceneTableError}</p>
            ) : null}
            {sceneTableLastSyncedAt ? (
              <p className="text-xs text-slate-500">Last synced {formatTimestamp(sceneTableLastSyncedAt)}</p>
            ) : null}
          </div>
          <div className="flex flex-col gap-4">
            <Card
              title="Status breakdown"
              description="Use badges to provide quick validation state overviews."
              footer="Status summaries will align with analytics from the validation engine."
            >
              <ul className="space-y-2 text-sm">
                {(["valid", "warnings", "errors"] as const).map((status) => (
                  <li
                    key={status}
                    className="flex items-center justify-between gap-3"
                  >
                    <ValidationStatusIndicator status={status} />
                    <span className="text-slate-300">
                      {formatSceneCountLabel(validationCounts[status])}
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
            <Card
              title="Design tokens"
              description="Cards and tables inherit Tailwind theme tokens for consistent surfaces."
              variant="subtle"
            >
              <p className="text-slate-300">
                Extend component variants by mapping new Tailwind utility combinations to semantic names. Theme updates can
                then roll out across the editor from a single location.
              </p>
            </Card>
          </div>
        </div>
      </EditorPanel>
    </>
  );
};

export default SceneLibraryPage;
