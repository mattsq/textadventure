import { create } from "zustand";
import {
  SceneEditorApiClient,
  SceneEditorApiError,
  type ListScenesParams,
  type SceneReferenceListResponse,
  type SceneReferenceResource,
  type SceneSummary,
  type TransitionResource,
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

export interface SceneDeletionState {
  readonly status: "idle" | "checking" | "ready" | "deleting" | "error";
  readonly scene: SceneTableRow | null;
  readonly references: readonly SceneReferenceResource[];
  readonly error: string | null;
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
  readonly sceneDeletionState: SceneDeletionState;

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
  readonly prepareSceneEdit: (scene: SceneTableRow) => void;
  readonly prepareSceneDuplicate: (scene: SceneTableRow) => void;
  readonly requestSceneDeletion: (
    client: SceneEditorApiClient,
    scene: SceneTableRow,
  ) => Promise<void>;
  readonly cancelSceneDeletion: () => void;
  readonly confirmSceneDeletion: (
    client: SceneEditorApiClient,
  ) => Promise<void>;
  readonly upsertSceneTableRow: (row: SceneTableRow) => void;
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

const DEFAULT_DELETION_STATE: SceneDeletionState = {
  status: "idle",
  scene: null,
  references: [],
  error: null,
};

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
  sceneDeletionState: DEFAULT_DELETION_STATE,
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
  prepareSceneEdit: (scene) =>
    set(() => ({
      sceneId: scene.id,
      sceneSummary: scene.description,
      statusMessage: `Loaded "${scene.id}" into the editor.`,
      navigationLog: `Editing scene "${scene.id}".`,
    })),
  prepareSceneDuplicate: (scene) => {
    const duplicateId = scene.id.endsWith("-copy")
      ? `${scene.id}-draft`
      : `${scene.id}-copy`;
    set(() => ({
      sceneId: duplicateId,
      sceneSummary: scene.description,
      statusMessage: `Prepared duplicate of "${scene.id}". Update the new ID before saving.`,
      navigationLog: `Duplicating scene "${scene.id}".`,
    }));
  },
  requestSceneDeletion: async (client, scene) => {
    set(() => ({
      statusMessage: `Checking references before deleting "${scene.id}"...`,
      navigationLog: `Delete action queued for "${scene.id}".`,
      sceneDeletionState: {
        status: "checking",
        scene,
        references: [],
        error: null,
      },
    }));

    try {
      const response: SceneReferenceListResponse =
        await client.listSceneReferences(scene.id);
      const references = response.data;

      set(() => ({
        sceneDeletionState: {
          status: "ready",
          scene,
          references,
          error: null,
        },
        statusMessage:
          references.length === 0
            ? `"${scene.id}" has no incoming references. Ready to confirm deletion.`
            : `Found ${references.length} reference${
                references.length === 1 ? "" : "s"
              } to "${scene.id}". Review the impact before deleting.`,
        navigationLog:
          references.length === 0
            ? `Deletion ready for "${scene.id}".`
            : `Deletion requires updating ${
                references.length === 1
                  ? "a dependent transition"
                  : "dependent transitions"
              } before removing "${scene.id}".`,
      }));
    } catch (error) {
      const message =
        error instanceof SceneEditorApiError
          ? error.message
          : `Unable to check references for "${scene.id}". Please try again.`;

      set(() => ({
        statusMessage: message,
        navigationLog: `Deletion check failed for "${scene.id}".`,
        sceneDeletionState: {
          status: "error",
          scene,
          references: [],
          error: message,
        },
      }));
    }
  },
  cancelSceneDeletion: () => {
    const { sceneDeletionState } = get();
    const cancelledSceneId = sceneDeletionState.scene?.id;
    set((state) => ({
      sceneDeletionState: DEFAULT_DELETION_STATE,
      statusMessage: cancelledSceneId
        ? `Deletion cancelled for "${cancelledSceneId}".`
        : state.statusMessage,
      navigationLog: cancelledSceneId
        ? `Deletion cancelled for "${cancelledSceneId}".`
        : state.navigationLog,
    }));
  },
  confirmSceneDeletion: async (client) => {
    const { sceneDeletionState } = get();
    if (sceneDeletionState.status === "error") {
      const scene = sceneDeletionState.scene;
      if (!scene) {
        return;
      }

      await get().requestSceneDeletion(client, scene);
      return;
    }

    if (sceneDeletionState.status !== "ready") {
      return;
    }

    const scene = sceneDeletionState.scene;
    if (!scene) {
      return;
    }

    const references = sceneDeletionState.references;

    set(() => ({
      statusMessage: references.length
        ? `Updating ${references.length} reference${
            references.length === 1 ? "" : "s"
          } before deleting "${scene.id}"...`
        : `Deleting "${scene.id}"...`,
      navigationLog: `Deletion workflow started for "${scene.id}".`,
      sceneDeletionState: {
        status: "deleting",
        scene,
        references,
        error: null,
      },
    }));

    try {
      const referencesByScene = new Map<
        string,
        SceneReferenceResource[]
      >();
      for (const reference of references) {
        const bucket = referencesByScene.get(reference.scene_id);
        if (bucket) {
          bucket.push(reference);
        } else {
          referencesByScene.set(reference.scene_id, [reference]);
        }
      }

      for (const [referencingSceneId, referencingCommands] of referencesByScene) {
        const detail = await client.getScene(referencingSceneId);
        const resource = detail.data;
        const nextTransitions: Record<string, TransitionResource> = {
          ...resource.transitions,
        };
        let mutated = false;

        for (const reference of referencingCommands) {
          const transition = nextTransitions[reference.command];
          if (transition && transition.target === scene.id) {
            nextTransitions[reference.command] = {
              ...transition,
              target: null,
            };
            mutated = true;
          }
        }

        if (!mutated) {
          continue;
        }

        await client.updateScene(referencingSceneId, {
          scene: {
            description: resource.description,
            choices: resource.choices,
            transitions: nextTransitions,
          },
        });
      }

      await client.deleteScene(scene.id);

      await get().loadSceneTable(client);

      set(() => ({
        sceneDeletionState: DEFAULT_DELETION_STATE,
        statusMessage:
          references.length === 0
            ? `Scene "${scene.id}" deleted successfully.`
            : `Scene "${scene.id}" deleted after clearing ${references.length} reference${
                references.length === 1 ? "" : "s"
              }.`,
        navigationLog: `Scene "${scene.id}" deleted via library view.`,
      }));
    } catch (error) {
      const message =
        error instanceof SceneEditorApiError
          ? error.message
          : `Unable to delete "${scene.id}". Please try again.`;

      set(() => ({
        statusMessage: message,
        navigationLog: `Deletion failed for "${scene.id}".`,
        sceneDeletionState: {
          status: "error",
          scene,
          references,
          error: message,
        },
      }));
    }
  },
  upsertSceneTableRow: (row) =>
    set((state) => {
      const previous = state.sceneTableState;
      const existingRows = previous.data ?? [];
      const nextRows = [
        {
          ...row,
          updatedAt: row.updatedAt,
        },
        ...existingRows.filter((existing) => existing.id !== row.id),
      ].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));

      const timestamp = new Date().toISOString();

      return {
        sceneTableState: {
          status: "success",
          data: nextRows,
          error: null,
          lastUpdatedAt: timestamp,
        },
        statusMessage: state.statusMessage,
      };
    }),
}));

export type { SceneSummary };
