import React from "react";
import { useNavigate } from "react-router-dom";
import {
  createSceneEditorApiClient,
  SceneEditorApiError,
  type TransitionResource,
} from "../api";
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
import { Pagination } from "../components/navigation";
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

const PAGE_SIZE_OPTIONS: readonly number[] = [25, 50, 100, 200];

type BulkActionType = "link" | "mark-terminal" | "clear-transition";

interface BulkStatusMessage {
  readonly type: "success" | "error" | "info";
  readonly message: string;
}

const BULK_STATUS_CLASSNAMES: Record<BulkStatusMessage["type"], string> = {
  success: "border-emerald-500/40 bg-emerald-500/10 text-emerald-100",
  error: "border-rose-500/40 bg-rose-500/10 text-rose-100",
  info: "border-indigo-400/40 bg-indigo-500/10 text-indigo-100",
};

const formatTimestamp = (value: string): string => {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString();
};

const standardizeCommand = (value: string): string => {
  const trimmed = value.trim().toLowerCase();
  if (trimmed === "") {
    return "";
  }

  const sanitized = trimmed
    .replace(/[^a-z0-9\s_-]/g, " ")
    .replace(/[\s_]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");

  return sanitized;
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
    page,
    pageSize,
    setSearchQuery,
    setValidationFilter,
    setTransitionFilter,
    setPage,
    setPageSize,
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

  const buildRowKey = React.useCallback(
    (row: ChoiceMatrixRow) => `${row.sceneId}:::${row.choiceCommand}`,
    [],
  );

  const [selectedRowIds, setSelectedRowIds] = React.useState<Set<string>>(
    () => new Set(),
  );

  const selectedRows = React.useMemo(
    () => matrixRows.filter((row) => selectedRowIds.has(buildRowKey(row))),
    [matrixRows, selectedRowIds, buildRowKey],
  );

  const selectedChoiceCount = selectedRows.length;

  const selectedSceneCount = React.useMemo(() => {
    const ids = new Set<string>();
    for (const row of selectedRows) {
      ids.add(row.sceneId);
    }

    return ids.size;
  }, [selectedRows]);

  const selectionSummary =
    selectedChoiceCount === 0
      ? "Select choices from the table to enable bulk actions."
      : `Selected ${selectedChoiceCount} ${
          selectedChoiceCount === 1 ? "choice" : "choices"
        } across ${selectedSceneCount} ${
          selectedSceneCount === 1 ? "scene" : "scenes"
        }.`;

  const availableSceneIds = React.useMemo(() => {
    const ids = new Set<string>();
    for (const row of matrixRows) {
      ids.add(row.sceneId);
      if (row.targetSceneId) {
        ids.add(row.targetSceneId);
      }
    }

    return Array.from(ids).sort((a, b) => a.localeCompare(b));
  }, [matrixRows]);

  const [bulkAction, setBulkAction] = React.useState<BulkActionType>("link");
  const [bulkTarget, setBulkTarget] = React.useState("");
  const [isApplyingBulkAction, setIsApplyingBulkAction] =
    React.useState(false);
  const [bulkStatus, setBulkStatus] = React.useState<BulkStatusMessage | null>(
    null,
  );
  const [isStandardizingCommands, setIsStandardizingCommands] =
    React.useState(false);
  const [standardizeStatus, setStandardizeStatus] =
    React.useState<BulkStatusMessage | null>(null);

  const standardizationCandidates = React.useMemo(() => {
    return selectedRows
      .map((row) => ({
        row,
        suggestion: standardizeCommand(row.choiceCommand),
      }))
      .filter(({ row, suggestion }) =>
        suggestion === "" ? false : suggestion !== row.choiceCommand,
      );
  }, [selectedRows]);

  const invalidStandardizationCommands = React.useMemo(() => {
    const invalid = new Set<string>();
    for (const row of selectedRows) {
      if (standardizeCommand(row.choiceCommand) === "") {
        invalid.add(row.choiceCommand);
      }
    }

    return Array.from(invalid).sort((a, b) => a.localeCompare(b));
  }, [selectedRows]);

  const standardizationPreview = React.useMemo(
    () => standardizationCandidates.slice(0, 5),
    [standardizationCandidates],
  );

  const remainingStandardizationCount =
    standardizationCandidates.length - standardizationPreview.length;

  React.useEffect(() => {
    setSelectedRowIds((previous) => {
      const validKeys = new Set(matrixRows.map(buildRowKey));
      let changed = false;
      const next = new Set<string>();

      previous.forEach((key) => {
        if (validKeys.has(key)) {
          next.add(key);
        } else {
          changed = true;
        }
      });

      return changed ? next : previous;
    });
  }, [matrixRows, buildRowKey]);

  const applyButtonLabel = isApplyingBulkAction
    ? "Applying…"
    : selectedChoiceCount === 0
    ? "Apply action"
    : `Apply to ${selectedChoiceCount} ${
        selectedChoiceCount === 1 ? "choice" : "choices"
      }`;
  const normalizedQuery = debouncedSearch.trim().toLowerCase();

  const standardizeButtonLabel = isStandardizingCommands
    ? "Standardizing…"
    : standardizationCandidates.length === 0
    ? "Standardize commands"
    : `Standardize ${standardizationCandidates.length} ${
        standardizationCandidates.length === 1 ? "command" : "commands"
      }`;

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

  const totalMatchingRows = filteredRows.length;
  const totalPages = Math.max(1, Math.ceil(totalMatchingRows / pageSize));
  const safePage = Math.max(1, Math.min(page, totalPages));
  const startIndex = totalMatchingRows === 0 ? 0 : (safePage - 1) * pageSize;
  const endIndex = totalMatchingRows === 0 ? 0 : Math.min(startIndex + pageSize, totalMatchingRows);
  const paginatedRows = React.useMemo(
    () => filteredRows.slice(startIndex, endIndex),
    [filteredRows, startIndex, endIndex],
  );

  const visibleRowKeys = React.useMemo(
    () => paginatedRows.map((row) => buildRowKey(row)),
    [paginatedRows, buildRowKey],
  );

  const allVisibleSelected =
    visibleRowKeys.length > 0 &&
    visibleRowKeys.every((key) => selectedRowIds.has(key));
  const someVisibleSelected = visibleRowKeys.some((key) =>
    selectedRowIds.has(key),
  );

  const selectionHeaderCheckboxRef = React.useRef<HTMLInputElement | null>(
    null,
  );

  React.useEffect(() => {
    if (selectionHeaderCheckboxRef.current) {
      selectionHeaderCheckboxRef.current.indeterminate =
        someVisibleSelected && !allVisibleSelected;
    }
  }, [someVisibleSelected, allVisibleSelected]);

  const toggleSingleRow = React.useCallback(
    (row: ChoiceMatrixRow) => {
      setSelectedRowIds((previous) => {
        const key = buildRowKey(row);
        const next = new Set(previous);
        if (next.has(key)) {
          next.delete(key);
        } else {
          next.add(key);
        }

        return next;
      });
    },
    [buildRowKey],
  );

  const handleSelectAllVisible = React.useCallback(() => {
    setSelectedRowIds((previous) => {
      const next = new Set(previous);
      if (visibleRowKeys.length === 0) {
        return previous;
      }

      if (allVisibleSelected) {
        visibleRowKeys.forEach((key) => next.delete(key));
      } else {
        visibleRowKeys.forEach((key) => next.add(key));
      }

      return next;
    });
  }, [allVisibleSelected, visibleRowKeys]);

  const handleClearSelection = React.useCallback(() => {
    setSelectedRowIds(() => new Set());
  }, []);

  const handleStandardizeCommands = React.useCallback(async () => {
    if (standardizationCandidates.length === 0) {
      setStandardizeStatus({
        type: "info",
        message:
          "Select choices with commands that need formatting before running standardization.",
      });
      return;
    }

    setIsStandardizingCommands(true);
    setStandardizeStatus(null);

    const updatesByScene = new Map<
      string,
      readonly { readonly row: ChoiceMatrixRow; readonly suggestion: string }[]
    >();

    for (const candidate of standardizationCandidates) {
      const existing = updatesByScene.get(candidate.row.sceneId);
      if (existing) {
        updatesByScene.set(candidate.row.sceneId, [...existing, candidate]);
      } else {
        updatesByScene.set(candidate.row.sceneId, [candidate]);
      }
    }

    try {
      let renamedCommandCount = 0;

      for (const [sceneId, updates] of updatesByScene.entries()) {
        let scene;
        try {
          const sceneResponse = await apiClient.getScene(sceneId);
          scene = sceneResponse.data;
        } catch (error) {
          const message =
            error instanceof SceneEditorApiError
              ? `Scene "${sceneId}": ${error.message}`
              : `Unable to load scene "${sceneId}". Please try again.`;
          setStandardizeStatus({ type: "error", message });
          return;
        }

        const updateMap = new Map<string, string>(
          updates.map(({ row, suggestion }) => [row.choiceCommand, suggestion]),
        );

        const occurrenceMap = new Map<string, number>();
        for (const suggestion of updateMap.values()) {
          occurrenceMap.set(
            suggestion,
            (occurrenceMap.get(suggestion) ?? 0) + 1,
          );
        }

        for (const [suggestion, count] of occurrenceMap.entries()) {
          if (count > 1) {
            setStandardizeStatus({
              type: "error",
              message: `Scene "${sceneId}": multiple commands would resolve to "${suggestion}". Adjust the selection and try again.`,
            });
            return;
          }
        }

        const existingCommands = new Set(
          scene.choices.map((choice) => choice.command),
        );

        for (const [oldCommand, newCommand] of updateMap.entries()) {
          if (
            newCommand !== oldCommand &&
            existingCommands.has(newCommand) &&
            !updateMap.has(newCommand)
          ) {
            setStandardizeStatus({
              type: "error",
              message: `Scene "${sceneId}": command "${newCommand}" already exists. Rename commands manually to resolve the conflict.`,
            });
            return;
          }
        }

        const updatedChoices = scene.choices.map((choice) => {
          const replacement = updateMap.get(choice.command);
          if (!replacement) {
            return choice;
          }

          return {
            ...choice,
            command: replacement,
          };
        });

        const updatedTransitions: Record<string, TransitionResource> = {};
        for (const [command, transition] of Object.entries(scene.transitions)) {
          const replacement = updateMap.get(command);
          updatedTransitions[replacement ?? command] = transition;
        }

        try {
          await apiClient.updateScene(sceneId, {
            scene: {
              description: scene.description,
              choices: updatedChoices.map((choice) => ({
                command: choice.command,
                description: choice.description,
              })),
              transitions: updatedTransitions,
            },
          });
        } catch (error) {
          const message =
            error instanceof SceneEditorApiError
              ? `Scene "${sceneId}": ${error.message}`
              : `Unable to update scene "${sceneId}". Please try again.`;
          setStandardizeStatus({ type: "error", message });
          return;
        }

        renamedCommandCount += updates.length;
      }

      setStandardizeStatus({
        type: "success",
        message: `Renamed ${renamedCommandCount} ${
          renamedCommandCount === 1 ? "command" : "commands"
        } across ${updatesByScene.size} ${
          updatesByScene.size === 1 ? "scene" : "scenes"
        }.`,
      });
      setSelectedRowIds(() => new Set());
      triggerLoad();
    } catch (error) {
      const message =
        error instanceof SceneEditorApiError
          ? error.message
          : "Unable to standardize commands. Please try again.";
      setStandardizeStatus({ type: "error", message });
    } finally {
      setIsStandardizingCommands(false);
    }
  }, [
    apiClient,
    setSelectedRowIds,
    standardizationCandidates,
    triggerLoad,
  ]);

  React.useEffect(() => {
    if (page !== safePage) {
      setPage(safePage);
    }
  }, [page, safePage, setPage]);

  React.useEffect(() => {
    setPage(1);
  }, [normalizedQuery, transitionFilter, validationFilter, setPage]);

  const resultsLabel =
    totalMatchingRows === 0
      ? "Showing 0 of 0 matching choices"
      : `Showing ${startIndex + 1}–${endIndex} of ${totalMatchingRows} matching choices`;

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

  const handlePageSizeChange = (
    event: React.ChangeEvent<HTMLSelectElement>,
  ) => {
    const nextSize = Number.parseInt(event.target.value, 10);
    if (!Number.isNaN(nextSize)) {
      setPageSize(nextSize);
    }
  };

  const handlePageChange = React.useCallback(
    (nextPage: number) => {
      setPage(nextPage);
    },
    [setPage],
  );

  const handleBulkActionChange = (
    event: React.ChangeEvent<HTMLSelectElement>,
  ) => {
    const value = event.target.value as BulkActionType;
    setBulkAction(value);
    if (value !== "link") {
      setBulkTarget("");
    }
  };

  const handleBulkTargetChange = (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
    setBulkTarget(event.target.value);
  };

  const getRowProps = React.useCallback(
    (row: ChoiceMatrixRow) => {
      const key = buildRowKey(row);
      if (!selectedRowIds.has(key)) {
        return undefined;
      }

      return {
        className: "bg-indigo-500/10 ring-1 ring-inset ring-indigo-500/40",
        "aria-selected": true,
      } as React.HTMLAttributes<HTMLTableRowElement>;
    },
    [buildRowKey, selectedRowIds],
  );

  const columns = React.useMemo(() => {
    const baseColumns = buildColumns(handleRowNavigate);
    const selectionColumn: DataTableColumn<ChoiceMatrixRow> = {
      id: "selection",
      header: (
        <label className="inline-flex items-center justify-center">
          <span className="sr-only">Select visible choices</span>
          <input
            ref={selectionHeaderCheckboxRef}
            type="checkbox"
            className="h-4 w-4 rounded border-slate-600 bg-slate-900 text-indigo-500 focus:ring-indigo-400"
            checked={visibleRowKeys.length > 0 && allVisibleSelected}
            onClick={(event) => event.stopPropagation()}
            onChange={(event) => {
              event.stopPropagation();
              handleSelectAllVisible();
            }}
            disabled={visibleRowKeys.length === 0}
          />
        </label>
      ),
      align: "center",
      className: "w-12",
      render: (row) => {
        const isSelected = selectedRowIds.has(buildRowKey(row));
        return (
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-slate-600 bg-slate-900 text-indigo-500 focus:ring-indigo-400"
            checked={isSelected}
            onClick={(event) => event.stopPropagation()}
            onChange={(event) => {
              event.stopPropagation();
              toggleSingleRow(row);
            }}
            aria-label={`Select choice ${row.choiceCommand} in scene ${row.sceneId}`}
          />
        );
      },
    };

    return [selectionColumn, ...baseColumns];
  }, [
    allVisibleSelected,
    buildRowKey,
    handleRowNavigate,
    handleSelectAllVisible,
    selectedRowIds,
    toggleSingleRow,
    visibleRowKeys.length,
  ]);

  const handleBulkActionSubmit = React.useCallback(
    async (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      setBulkStatus(null);

      if (selectedRowIds.size === 0) {
        setBulkStatus({
          type: "error",
          message:
            "Select at least one choice before applying a bulk action.",
        });
        return;
      }

      const trimmedTarget = bulkTarget.trim();

      if (bulkAction === "link" && trimmedTarget === "") {
        setBulkStatus({
          type: "error",
          message: "Enter a target scene identifier before linking choices.",
        });
        return;
      }

      const rowsToUpdate = matrixRows.filter((row) =>
        selectedRowIds.has(buildRowKey(row)),
      );

      if (rowsToUpdate.length === 0) {
        setBulkStatus({
          type: "info",
          message:
            "No matching choices remain after applying the current filters.",
        });
        return;
      }

      setIsApplyingBulkAction(true);

      let updatedChoiceCount = 0;
      let updatedSceneCount = 0;

      try {
        const grouped = new Map<string, ChoiceMatrixRow[]>();
        for (const row of rowsToUpdate) {
          const bucket = grouped.get(row.sceneId) ?? [];
          bucket.push(row);
          grouped.set(row.sceneId, bucket);
        }

        for (const [sceneId, rows] of grouped) {
          const sceneResponse = await apiClient.getScene(sceneId);
          const scene = sceneResponse.data;

          const nextTransitions: Record<string, TransitionResource> =
            Object.fromEntries(
              Object.entries(scene.transitions).map(
                ([command, transition]) => [
                  command,
                  {
                    ...transition,
                    target: transition.target ?? null,
                    narration: transition.narration ?? "",
                  },
                ],
              ),
            );

          let sceneUpdatedCount = 0;

          for (const row of rows) {
            const command = row.choiceCommand;

            if (bulkAction === "clear-transition") {
              if (
                Object.prototype.hasOwnProperty.call(nextTransitions, command)
              ) {
                delete nextTransitions[command];
                sceneUpdatedCount += 1;
              }
              continue;
            }

            const existing = nextTransitions[command];
            const baseTransition: TransitionResource = existing
              ? {
                  ...existing,
                  target: existing.target ?? null,
                  narration: existing.narration ?? "",
                }
              : { target: null, narration: "" };

            if (bulkAction === "link") {
              if (baseTransition.target === trimmedTarget) {
                continue;
              }

              nextTransitions[command] = {
                ...baseTransition,
                target: trimmedTarget,
              };
              sceneUpdatedCount += 1;
              continue;
            }

            if (existing && (existing.target ?? null) === null) {
              continue;
            }

            nextTransitions[command] = {
              ...baseTransition,
              target: null,
            };
            sceneUpdatedCount += 1;
          }

          if (sceneUpdatedCount === 0) {
            continue;
          }

          try {
            await apiClient.updateScene(sceneId, {
              scene: {
                description: scene.description,
                choices: scene.choices.map((choice) => ({
                  command: choice.command,
                  description: choice.description,
                })),
                transitions: nextTransitions,
              },
            });
          } catch (error) {
            const message =
              error instanceof SceneEditorApiError
                ? `Scene "${sceneId}": ${error.message}`
                : `Unable to update scene "${sceneId}". Please try again.`;
            setBulkStatus({ type: "error", message });
            return;
          }

          updatedChoiceCount += sceneUpdatedCount;
          updatedSceneCount += 1;
        }

        if (updatedChoiceCount === 0) {
          setBulkStatus({
            type: "info",
            message:
              "No changes were required. The selected choices already matched the requested state.",
          });
          return;
        }

        setBulkStatus({
          type: "success",
          message: `Updated ${updatedChoiceCount} ${
            updatedChoiceCount === 1 ? "choice" : "choices"
          } across ${updatedSceneCount} ${
            updatedSceneCount === 1 ? "scene" : "scenes"
          }.`,
        });
        setSelectedRowIds(() => new Set());
        if (bulkAction === "link") {
          setBulkTarget("");
        }
        triggerLoad();
      } catch (error) {
        const message =
          error instanceof SceneEditorApiError
            ? error.message
            : "Unable to apply the bulk action. Please try again.";
        setBulkStatus({ type: "error", message });
      } finally {
        setIsApplyingBulkAction(false);
      }
    },
    [
      apiClient,
      bulkAction,
      bulkTarget,
      buildRowKey,
      matrixRows,
      selectedRowIds,
      triggerLoad,
    ],
  );

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
        <div className="space-y-4">
          <form
            onSubmit={handleBulkActionSubmit}
            className="space-y-4 rounded-lg border border-slate-800/60 bg-slate-900/40 p-4"
          >
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h3 className="text-sm font-semibold text-white">Bulk actions</h3>
                <p className="text-xs text-slate-300">{selectionSummary}</p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={handleClearSelection}
                  className="inline-flex items-center gap-1 rounded border border-slate-600/70 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-slate-200 transition hover:border-slate-500 hover:bg-slate-800/60 disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={selectedRowIds.size === 0 || isApplyingBulkAction}
                >
                  Clear selection
                </button>
                <button
                  type="submit"
                  className="inline-flex items-center gap-2 rounded bg-indigo-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={selectedRowIds.size === 0 || isApplyingBulkAction}
                >
                  {applyButtonLabel}
                </button>
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              <SelectField
                label="Bulk action"
                value={bulkAction}
                onChange={handleBulkActionChange}
                disabled={isApplyingBulkAction}
              >
                <option value="link">Link to scene</option>
                <option value="mark-terminal">Mark as terminal ending</option>
                <option value="clear-transition">Remove transition link</option>
              </SelectField>
              {bulkAction === "link" ? (
                <div className="md:col-span-2 lg:col-span-2">
                  <TextField
                    id="bulk-target-scene"
                    label="Target scene identifier"
                    placeholder="Enter a scene ID to link to"
                    value={bulkTarget}
                    onChange={handleBulkTargetChange}
                    list="bulk-target-options"
                    required
                    disabled={isApplyingBulkAction}
                    description="Link all selected choices to this destination scene."
                  />
                  <datalist id="bulk-target-options">
                    {availableSceneIds.map((sceneId) => (
                      <option key={sceneId} value={sceneId} />
                    ))}
                  </datalist>
                </div>
              ) : null}
            </div>
            {bulkStatus ? (
              <div
                role="status"
                className={`rounded-lg border px-3 py-2 text-xs font-medium ${BULK_STATUS_CLASSNAMES[bulkStatus.type]}`}
              >
                {bulkStatus.message}
              </div>
            ) : null}
          </form>
          <div className="space-y-3 rounded-lg border border-indigo-500/40 bg-indigo-500/10 p-4">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h3 className="text-sm font-semibold text-white">Command standardization</h3>
                <p className="text-xs text-slate-200">
                  Convert selected commands to kebab-case to keep player input consistent across the adventure.
                </p>
              </div>
              <button
                type="button"
                onClick={handleStandardizeCommands}
                className="inline-flex items-center gap-2 rounded bg-indigo-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={
                  isStandardizingCommands || standardizationCandidates.length === 0
                }
              >
                {standardizeButtonLabel}
              </button>
            </div>
            {standardizationPreview.length > 0 ? (
              <ul className="space-y-2 text-xs text-slate-100">
                {standardizationPreview.map(({ row, suggestion }) => (
                  <li
                    key={`${row.sceneId}:::${row.choiceCommand}`}
                    className="flex flex-wrap items-center gap-2"
                  >
                    <span className="inline-flex items-center gap-2">
                      <code className="rounded bg-slate-900/70 px-2 py-1 font-mono text-[0.65rem] uppercase tracking-wide">
                        {row.choiceCommand}
                      </code>
                      <span aria-hidden className="text-slate-400">
                        →
                      </span>
                      <code className="rounded bg-emerald-600/20 px-2 py-1 font-mono text-[0.65rem] uppercase tracking-wide text-emerald-200">
                        {suggestion}
                      </code>
                    </span>
                    <span className="text-[0.65rem] uppercase tracking-wide text-indigo-200/80">
                      {row.sceneId}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-slate-300">
                Select choices with inconsistent commands to preview suggested updates.
              </p>
            )}
            {remainingStandardizationCount > 0 ? (
              <p className="text-[0.7rem] text-slate-300">
                +{remainingStandardizationCount} additional {" "}
                {remainingStandardizationCount === 1 ? "command" : "commands"} ready for renaming.
              </p>
            ) : null}
            {invalidStandardizationCommands.length > 0 ? (
              <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-100">
                Unable to generate kebab-case commands for: {invalidStandardizationCommands.join(", ")}. Update these manually.
              </div>
            ) : null}
            {standardizeStatus ? (
              <div
                role="status"
                className={`rounded-lg border px-3 py-2 text-xs font-medium ${BULK_STATUS_CLASSNAMES[standardizeStatus.type]}`}
              >
                {standardizeStatus.message}
              </div>
            ) : null}
          </div>
          <DataTable
            columns={columns}
            data={paginatedRows}
            getRowKey={(row) => buildRowKey(row)}
            onRowClick={handleRowNavigate}
            getRowProps={getRowProps}
            emptyState={
              matrixState.status === "loading"
                ? "Loading choice data..."
                : "No choices match the current filters."
            }
          />
          <div className="flex flex-col gap-4 border-t border-slate-800/60 pt-4 md:flex-row md:items-center md:justify-between">
            <span className="text-xs text-slate-300">{resultsLabel}</span>
            <div className="flex flex-col items-stretch gap-3 sm:flex-row sm:items-center sm:gap-4">
              <SelectField
                label="Rows per page"
                value={String(pageSize)}
                onChange={handlePageSizeChange}
                className="sm:w-44"
              >
                {PAGE_SIZE_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option} rows
                  </option>
                ))}
              </SelectField>
              <Pagination
                currentPage={safePage}
                totalPages={totalPages}
                onPageChange={handlePageChange}
              />
            </div>
          </div>
        </div>
      </EditorPanel>
    </div>
  );
};

export default ChoiceMatrixPage;
