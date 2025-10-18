import { create } from "zustand";
import type { SceneEditorApiClient, SceneSummary, SceneResource } from "../api";
import { SceneEditorApiError } from "../api";
import {
  type AsyncState,
  type SceneTableValidationFilter,
  type ValidationState,
} from "./sceneEditorStore";

export type ChoiceMatrixTransitionType = "linked" | "terminal" | "unlinked";

export interface ChoiceMatrixRow {
  readonly sceneId: string;
  readonly sceneDescription: string;
  readonly validationStatus: ValidationState;
  readonly sceneChoiceCount: number;
  readonly sceneTransitionCount: number;
  readonly choiceCommand: string;
  readonly choiceDescription: string;
  readonly transitionType: ChoiceMatrixTransitionType;
  readonly targetSceneId: string | null;
  readonly updatedAt: string;
}

export type ChoiceMatrixTransitionFilter =
  | "all"
  | ChoiceMatrixTransitionType;

export interface ChoiceMatrixState {
  readonly matrixState: AsyncState<ChoiceMatrixRow[]>;
  readonly searchQuery: string;
  readonly validationFilter: SceneTableValidationFilter;
  readonly transitionFilter: ChoiceMatrixTransitionFilter;
  readonly setSearchQuery: (value: string) => void;
  readonly setValidationFilter: (
    value: SceneTableValidationFilter,
  ) => void;
  readonly setTransitionFilter: (
    value: ChoiceMatrixTransitionFilter,
  ) => void;
  readonly loadChoiceMatrix: (
    client: SceneEditorApiClient,
    options?: { signal?: AbortSignal }
  ) => Promise<void>;
}

const mapTransitionType = (
  transition: SceneResource["transitions"][string] | undefined,
): ChoiceMatrixTransitionType => {
  if (!transition) {
    return "unlinked";
  }

  if (transition.target === null || transition.target === undefined) {
    return "terminal";
  }

  return "linked";
};

const mapSceneToRows = (
  summary: SceneSummary,
  scene: SceneResource,
): ChoiceMatrixRow[] =>
  scene.choices.map((choice) => {
    const transition = scene.transitions[choice.command];
    return {
      sceneId: scene.id,
      sceneDescription: summary.description,
      validationStatus: summary.validation_status,
      sceneChoiceCount: summary.choice_count,
      sceneTransitionCount: summary.transition_count,
      choiceCommand: choice.command,
      choiceDescription: choice.description,
      transitionType: mapTransitionType(transition),
      targetSceneId: transition?.target ?? null,
      updatedAt: summary.updated_at,
    };
  });

const DEFAULT_MATRIX_ROWS: ChoiceMatrixRow[] = [
  {
    sceneId: "mysterious-grove",
    sceneDescription: "A moonlit clearing reveals a hidden ritual site.",
    validationStatus: "valid",
    sceneChoiceCount: 3,
    sceneTransitionCount: 4,
    choiceCommand: "inspect-altar",
    choiceDescription: "Inspect the altar's carvings for hidden messages.",
    transitionType: "linked",
    targetSceneId: "shrouded-altar",
    updatedAt: "2024-06-01T12:00:00Z",
  },
  {
    sceneId: "mysterious-grove",
    sceneDescription: "A moonlit clearing reveals a hidden ritual site.",
    validationStatus: "valid",
    sceneChoiceCount: 3,
    sceneTransitionCount: 4,
    choiceCommand: "circle-perimeter",
    choiceDescription: "Patrol the grove's edge in search of watchers.",
    transitionType: "unlinked",
    targetSceneId: null,
    updatedAt: "2024-06-01T12:00:00Z",
  },
  {
    sceneId: "shrouded-altar",
    sceneDescription: "An ancient altar hums with latent energy.",
    validationStatus: "warnings",
    sceneChoiceCount: 2,
    sceneTransitionCount: 3,
    choiceCommand: "complete-ritual",
    choiceDescription: "Attempt to finish the lunar ritual despite the risks.",
    transitionType: "terminal",
    targetSceneId: null,
    updatedAt: "2024-06-01T11:43:00Z",
  },
];

export const useChoiceMatrixStore = create<ChoiceMatrixState>((set, get) => ({
  matrixState: {
    status: "success",
    data: DEFAULT_MATRIX_ROWS,
    error: null,
    lastUpdatedAt: null,
  },
  searchQuery: "",
  validationFilter: "all",
  transitionFilter: "all",
  setSearchQuery: (value) => set({ searchQuery: value }),
  setValidationFilter: (value) => set({ validationFilter: value }),
  setTransitionFilter: (value) => set({ transitionFilter: value }),
  loadChoiceMatrix: async (client, options = {}) => {
    const previous = get().matrixState;
    set({
      matrixState: {
        status: "loading",
        data: previous.data,
        error: null,
        lastUpdatedAt: previous.lastUpdatedAt,
      },
    });

    try {
      const response = await client.listScenes({
        include_validation: true,
        page_size: 200,
        signal: options.signal,
      });

      const sceneResults = await Promise.all(
        response.data.map(async (summary) => {
          const resource = await client.getScene(summary.id, {
            signal: options.signal,
          });
          return mapSceneToRows(summary, resource.data);
        }),
      );

      const rows = sceneResults.flat();

      set({
        matrixState: {
          status: "success",
          data: rows,
          error: null,
          lastUpdatedAt: new Date().toISOString(),
        },
      });
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        return;
      }

      const message =
        error instanceof SceneEditorApiError
          ? error.message
          : "Unable to load the choice matrix. Please try again.";

      set({
        matrixState: {
          status: "error",
          data: previous.data,
          error: message,
          lastUpdatedAt: previous.lastUpdatedAt,
        },
      });
    }
  },
}));

export default useChoiceMatrixStore;
