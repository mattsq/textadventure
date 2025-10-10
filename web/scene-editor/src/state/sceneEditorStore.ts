import { create } from "zustand";
import {
  SceneEditorApiClient,
  SceneEditorApiError,
  type ListScenesParams,
  type SceneSummary,
} from "../api";

export const PRIMARY_TAB_IDS = ["details", "choices", "testing"] as const;
export type PrimaryTabId = (typeof PRIMARY_TAB_IDS)[number];

export const INSPECTOR_TAB_IDS = [
  "overview",
  "validation",
  "activity",
] as const;
export type InspectorTabId = (typeof INSPECTOR_TAB_IDS)[number];

export type ValidationState = "valid" | "warnings" | "errors";

export type SceneTableValidationFilter = "all" | ValidationState;

export type AsyncStatus = "idle" | "loading" | "success" | "error";

export interface AsyncState<TData> {
  readonly status: AsyncStatus;
  readonly data: TData | null;
  readonly error: string | null;
  readonly lastUpdatedAt: string | null;
}

export interface SceneTableRow {
  readonly id: string;
  readonly description: string;
  readonly choiceCount: number;
  readonly transitionCount: number;
  readonly hasTerminalTransition: boolean;
  readonly validationStatus: ValidationState;
  readonly updatedAt: string;
}

export interface SceneEditorState {
  readonly sceneId: string;
  readonly sceneType: string;
  readonly sceneSummary: string;
  readonly statusMessage: string | null;
  readonly navigationLog: string;
  readonly activePrimaryTab: PrimaryTabId;
  readonly activeInspectorTab: InspectorTabId;
  readonly sceneTableState: AsyncState<SceneTableRow[]>;
  readonly sceneTableQuery: string;
  readonly sceneTableValidationFilter: SceneTableValidationFilter;

  readonly setSceneId: (value: string) => void;
  readonly setSceneType: (value: string) => void;
  readonly setSceneSummary: (value: string) => void;
  readonly setStatusMessage: (value: string | null) => void;
  readonly setNavigationLog: (value: string) => void;
  readonly setActivePrimaryTab: (tabId: PrimaryTabId, logMessage: string) => void;
  readonly setActiveInspectorTab: (
    tabId: InspectorTabId,
    logMessage: string,
  ) => void;
  readonly setSceneTableQuery: (value: string) => void;
  readonly setSceneTableValidationFilter: (
    value: SceneTableValidationFilter,
  ) => void;
  readonly loadSceneTable: (
    client: SceneEditorApiClient,
    params?: ListScenesParams,
  ) => Promise<void>;
}

const mapSceneSummaryToRow = (summary: SceneSummary): SceneTableRow => ({
  id: summary.id,
  description: summary.description,
  choiceCount: summary.choice_count,
  transitionCount: summary.transition_count,
  hasTerminalTransition: summary.has_terminal_transition,
  validationStatus: summary.validation_status,
  updatedAt: summary.updated_at,
});

const defaultSceneTableRows: SceneTableRow[] = [
  {
    id: "mysterious-grove",
    description: "A moonlit clearing reveals a hidden ritual site.",
    choiceCount: 3,
    transitionCount: 4,
    hasTerminalTransition: false,
    validationStatus: "valid",
    updatedAt: "2024-06-01T12:00:00Z",
  },
  {
    id: "shrouded-altar",
    description: "An ancient altar hums with latent energy.",
    choiceCount: 2,
    transitionCount: 3,
    hasTerminalTransition: false,
    validationStatus: "warnings",
    updatedAt: "2024-06-01T11:43:00Z",
  },
  {
    id: "lunar-eclipse",
    description: "The ritual reaches its climax beneath the eclipsed moon.",
    choiceCount: 1,
    transitionCount: 1,
    hasTerminalTransition: true,
    validationStatus: "errors",
    updatedAt: "2024-05-31T22:15:00Z",
  },
];

const resetStatus = () => ({ statusMessage: null as string | null });

export const useSceneEditorStore = create<SceneEditorState>((set, get) => ({
  sceneId: "mysterious-grove",
  sceneType: "branch",
  sceneSummary: "A moonlit clearing reveals a hidden ritual site.",
  statusMessage: null,
  navigationLog:
    "Primary navigation focused on scene metadata and narrative notes.",
  activePrimaryTab: "details",
  activeInspectorTab: "overview",
  sceneTableState: {
    status: "success",
    data: defaultSceneTableRows,
    error: null,
    lastUpdatedAt: null,
  },
  sceneTableQuery: "",
  sceneTableValidationFilter: "all",
  setSceneId: (value) =>
    set(() => ({
      sceneId: value,
      ...resetStatus(),
    })),
  setSceneType: (value) =>
    set(() => ({
      sceneType: value,
      ...resetStatus(),
    })),
  setSceneSummary: (value) =>
    set(() => ({
      sceneSummary: value,
      ...resetStatus(),
    })),
  setStatusMessage: (value) => set(() => ({ statusMessage: value })),
  setNavigationLog: (value) => set(() => ({ navigationLog: value })),
  setActivePrimaryTab: (tabId, logMessage) =>
    set(() => ({ activePrimaryTab: tabId, navigationLog: logMessage })),
  setActiveInspectorTab: (tabId, logMessage) =>
    set(() => ({ activeInspectorTab: tabId, navigationLog: logMessage })),
  setSceneTableQuery: (value) =>
    set(() => ({
      sceneTableQuery: value,
      statusMessage: null,
    })),
  setSceneTableValidationFilter: (value) =>
    set(() => ({
      sceneTableValidationFilter: value,
      statusMessage: null,
    })),
  loadSceneTable: async (client, params = {}) => {
    const previous = get().sceneTableState;
    const { sceneTableQuery } = get();
    const { search: searchOverride, ...restParams } = params;
    const resolvedQuery =
      typeof searchOverride === "string"
        ? searchOverride.trim()
        : sceneTableQuery.trim();
    const search = resolvedQuery ? resolvedQuery : undefined;
    set(() => ({
      sceneTableState: {
        status: "loading",
        data: previous.data,
        error: null,
        lastUpdatedAt: previous.lastUpdatedAt,
      },
      statusMessage: null,
    }));

    try {
      const response = await client.listScenes({
        include_validation: true,
        ...restParams,
        search,
      });
      const rows = response.data.map(mapSceneSummaryToRow);
      set(() => ({
        sceneTableState: {
          status: "success",
          data: rows,
          error: null,
          lastUpdatedAt: new Date().toISOString(),
        },
        statusMessage: null,
      }));
    } catch (error) {
      const message =
        error instanceof SceneEditorApiError
          ? error.message
          : "Unable to load scenes. Please try again.";

      set(() => ({
        sceneTableState: {
          status: "error",
          data: previous.data,
          error: message,
          lastUpdatedAt: previous.lastUpdatedAt,
        },
        statusMessage: message,
      }));
    }
  },
}));

export type { SceneSummary };
