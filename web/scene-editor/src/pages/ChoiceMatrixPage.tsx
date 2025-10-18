import React from "react";
import { useNavigate } from "react-router-dom";
import { createSceneEditorApiClient } from "../api";
import {
  Badge,
  Card,
  DataTable,
  SceneMetadataCell,
  ValidationStatusIndicator,
  VALIDATION_STATUS_DESCRIPTORS,
  type DataTableColumn,
} from "../components/display";
import { EditorPanel } from "../components/layout";
import { SelectField, TextField } from "../components/forms";
import {
  type ChoiceMatrixRow,
  type ChoiceMatrixTransitionFilter,
  type ChoiceMatrixTransitionType,
  type SceneTableValidationFilter,
  useChoiceMatrixStore,
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

const transitionFilterLabels: Record<ChoiceMatrixTransitionFilter, string> = {
  all: "All transitions",
  linked: "Linked transitions",
  terminal: "Terminal endings",
  unlinked: "Missing transitions",
};

const transitionFilterOptions: readonly ChoiceMatrixTransitionFilter[] = [
  "all",
  "linked",
  "terminal",
  "unlinked",
];

const transitionVariantMap: Record<ChoiceMatrixTransitionType, React.ComponentProps<typeof Badge>["variant"]> = {
  linked: "success",
  terminal: "info",
  unlinked: "danger",
};

const transitionLabelMap: Record<ChoiceMatrixTransitionType, string> = {
  linked: "Linked",
  terminal: "Terminal",
  unlinked: "Unlinked",
};

const transitionDescriptionMap: Record<ChoiceMatrixTransitionType, string> = {
  linked: "This choice connects to another scene.",
  terminal: "This choice ends the adventure.",
  unlinked: "No transition is linked to this choice yet.",
};

const formatTimestamp = (value: string): string => {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString();
};

const buildColumns = (
  onRowClick: (row: ChoiceMatrixRow) => void,
): readonly DataTableColumn<ChoiceMatrixRow>[] => [
  {
    id: "scene",
    header: "Scene",
    className: "align-top",
    render: (row) => (
      <SceneMetadataCell
        id={row.sceneId}
        description={row.sceneDescription}
        choiceCount={row.sceneChoiceCount}
        transitionCount={row.sceneTransitionCount}
      />
    ),
  },
  {
    id: "validation",
    header: "Validation",
    align: "center",
    render: (row) => <ValidationStatusIndicator status={row.validationStatus} />,
  },
  {
    id: "command",
    header: "Command",
    className: "align-top",
    render: (row) => (
      <button
        type="button"
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          onRowClick(row);
        }}
        className="inline-flex items-center gap-2 text-left text-indigo-100 transition hover:text-white"
      >
        <code className="rounded bg-slate-900/70 px-2 py-1 text-xs font-semibold uppercase tracking-wide">
          {row.choiceCommand}
        </code>
      </button>
    ),
  },
  {
    id: "description",
    header: "Description",
    className: "max-w-sm align-top",
    render: (row) => <p className="text-sm leading-relaxed text-slate-200">{row.choiceDescription}</p>,
  },
  {
    id: "transition",
    header: "Transition",
    align: "center",
    render: (row) => (
      <Badge
        variant={transitionVariantMap[row.transitionType]}
        size="sm"
        title={transitionDescriptionMap[row.transitionType]}
      >
        {transitionLabelMap[row.transitionType]}
      </Badge>
    ),
  },
  {
    id: "target",
    header: "Target",
    className: "align-top",
    render: (row) => {
      if (row.transitionType === "linked" && row.targetSceneId) {
        return (
          <button
            type="button"
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              onRowClick(row);
            }}
            className="inline-flex items-center gap-1 rounded border border-indigo-500/40 bg-indigo-500/10 px-2 py-1 text-xs font-semibold text-indigo-100 transition hover:border-indigo-400/60 hover:bg-indigo-500/20"
          >
            <span className="font-mono">{row.targetSceneId}</span>
            <span aria-hidden>↗</span>
          </button>
        );
      }

      if (row.transitionType === "terminal") {
        return <span className="text-xs text-slate-300">Terminal outcome</span>;
      }

      return <span className="text-xs text-rose-200">No target linked</span>;
    },
  },
  {
    id: "updated",
    header: "Updated",
    align: "right",
    render: (row) => (
      <span className="font-mono text-xs text-slate-400">{formatTimestamp(row.updatedAt)}</span>
    ),
  },
];

export const ChoiceMatrixPage: React.FC = () => {
  const navigate = useNavigate();
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

  const {
    matrixState,
    searchQuery,
    validationFilter,
    transitionFilter,
    setSearchQuery,
    setValidationFilter,
    setTransitionFilter,
    loadChoiceMatrix,
  } = useChoiceMatrixStore();

  const abortControllerRef = React.useRef<AbortController | null>(null);

  const triggerLoad = React.useCallback(() => {
    abortControllerRef.current?.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;
    void loadChoiceMatrix(apiClient, { signal: controller.signal });
  }, [apiClient, loadChoiceMatrix]);

  React.useEffect(() => {
    triggerLoad();

    return () => {
      abortControllerRef.current?.abort();
    };
  }, [triggerLoad]);

  const handleRowNavigate = React.useCallback(
    (row: ChoiceMatrixRow) => {
      navigate(`/scenes/${encodeURIComponent(row.sceneId)}`);
    },
    [navigate],
  );

  const columns = React.useMemo(
    () => buildColumns(handleRowNavigate),
    [handleRowNavigate],
  );

  const [debouncedSearch, setDebouncedSearch] = React.useState(searchQuery);

  React.useEffect(() => {
    const handle = setTimeout(() => {
      setDebouncedSearch(searchQuery);
    }, 250);

    return () => {
      clearTimeout(handle);
    };
  }, [searchQuery]);

  const matrixRows = matrixState.data ?? [];
  const normalizedQuery = debouncedSearch.trim().toLowerCase();

  const filteredRows = React.useMemo(() => {
    return matrixRows.filter((row) => {
      if (
        validationFilter !== "all" &&
        row.validationStatus !== validationFilter
      ) {
        return false;
      }

      if (
        transitionFilter !== "all" &&
        row.transitionType !== transitionFilter
      ) {
        return false;
      }

      if (!normalizedQuery) {
        return true;
      }

      const haystacks = [
        row.sceneId,
        row.sceneDescription,
        row.choiceCommand,
        row.choiceDescription,
        row.targetSceneId ?? "",
      ];

      return haystacks.some((value) =>
        value.toLowerCase().includes(normalizedQuery),
      );
    });
  }, [matrixRows, normalizedQuery, transitionFilter, validationFilter]);

  const sceneCount = React.useMemo(() => new Set(matrixRows.map((row) => row.sceneId)).size, [matrixRows]);
  const linkedCount = matrixRows.filter((row) => row.transitionType === "linked").length;
  const terminalCount = matrixRows.filter((row) => row.transitionType === "terminal").length;
  const unlinkedCount = matrixRows.filter((row) => row.transitionType === "unlinked").length;

  const statusBadge = React.useMemo(() => {
    if (matrixState.status === "loading") {
      return (
        <Badge variant="info" size="sm" className="uppercase tracking-wide">
          Loading…
        </Badge>
      );
    }

    if (matrixState.status === "error") {
      return (
        <Badge variant="danger" size="sm" className="uppercase tracking-wide">
          Using cached data
        </Badge>
      );
    }

    return (
      <Badge variant="success" size="sm" className="uppercase tracking-wide">
        Synced
      </Badge>
    );
  }, [matrixState.status]);

  const lastUpdatedLabel = React.useMemo(() => {
    if (!matrixState.lastUpdatedAt) {
      return "Never refreshed";
    }

    return `Updated ${formatTimestamp(matrixState.lastUpdatedAt)}`;
  }, [matrixState.lastUpdatedAt]);

  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(event.target.value);
  };

  const handleValidationFilterChange = (
    event: React.ChangeEvent<HTMLSelectElement>,
  ) => {
    setValidationFilter(event.target.value as SceneTableValidationFilter);
  };

  const handleTransitionFilterChange = (
    event: React.ChangeEvent<HTMLSelectElement>,
  ) => {
    setTransitionFilter(event.target.value as ChoiceMatrixTransitionFilter);
  };

  return (
    <div className="space-y-8">
      <EditorPanel
        title="Choice Matrix"
        description="Review every choice across the adventure, identify gaps in transition coverage, and jump straight into scene editing when action is required."
        actions={
          <div className="flex items-center gap-3 text-xs text-slate-300">
            {statusBadge}
            <span className="font-mono text-slate-400">{lastUpdatedLabel}</span>
            <button
              type="button"
              onClick={triggerLoad}
              className="inline-flex items-center gap-1 rounded border border-indigo-400/50 bg-indigo-500/20 px-3 py-1 font-semibold text-indigo-100 transition hover:border-indigo-300/80 hover:bg-indigo-500/30"
            >
              Refresh
            </button>
          </div>
        }
      >
        {matrixState.error ? (
          <div
            role="alert"
            className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-100"
          >
            {matrixState.error}
          </div>
        ) : null}

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <Card
            compact
            variant="subtle"
            title="Scenes tracked"
            description="Unique scenes represented in the matrix."
          >
            <span className="text-2xl font-semibold text-white">{sceneCount}</span>
            <span className="text-xs text-slate-400">{matrixRows.length} total choices</span>
          </Card>
          <Card
            compact
            variant="subtle"
            title="Linked transitions"
            description="Choices that flow into another scene."
          >
            <span className="text-2xl font-semibold text-emerald-200">{linkedCount}</span>
            <span className="text-xs text-slate-400">Ensure narration aligns with the destination.</span>
          </Card>
          <Card
            compact
            variant="subtle"
            title="Terminal endings"
            description="Choices that conclude the narrative."
          >
            <span className="text-2xl font-semibold text-sky-200">{terminalCount}</span>
            <span className="text-xs text-slate-400">Verify endings include satisfying closure.</span>
          </Card>
          <Card
            compact
            variant="subtle"
            title="Unlinked choices"
            description="Commands without a destination yet."
          >
            <span className="text-2xl font-semibold text-rose-200">{unlinkedCount}</span>
            <span className="text-xs text-slate-400">Prioritise adding transitions or retiring these choices.</span>
          </Card>
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <TextField
            label="Search choices"
            placeholder="Search by scene, command, or description"
            value={searchQuery}
            onChange={handleSearchChange}
          />
          <SelectField
            label="Validation status"
            value={validationFilter}
            onChange={handleValidationFilterChange}
          >
            {validationFilterOptions.map((option) => (
              <option key={option} value={option}>
                {validationFilterLabels[option]}
              </option>
            ))}
          </SelectField>
          <SelectField
            label="Transition coverage"
            value={transitionFilter}
            onChange={handleTransitionFilterChange}
          >
            {transitionFilterOptions.map((option) => (
              <option key={option} value={option}>
                {transitionFilterLabels[option]}
              </option>
            ))}
          </SelectField>
        </div>
      </EditorPanel>

      <EditorPanel
        variant="subtle"
        title="Scene choice overview"
        description="Click any command or target to open the associated scene for deeper editing."
      >
        <DataTable
          columns={columns}
          data={filteredRows}
          getRowKey={(row) => `${row.sceneId}-${row.choiceCommand}`}
          onRowClick={handleRowNavigate}
          emptyState={
            matrixState.status === "loading"
              ? "Loading choice data..."
              : "No choices match the current filters."
          }
        />
      </EditorPanel>
    </div>
  );
};

export default ChoiceMatrixPage;
