import { create } from "zustand";

export const PRIMARY_TAB_IDS = ["details", "choices", "testing"] as const;
export type PrimaryTabId = (typeof PRIMARY_TAB_IDS)[number];

export const INSPECTOR_TAB_IDS = [
  "overview",
  "validation",
  "activity",
] as const;
export type InspectorTabId = (typeof INSPECTOR_TAB_IDS)[number];

type ValidationState = "clean" | "warnings" | "errors";

export interface SceneTableRow {
  readonly id: string;
  readonly title: string;
  readonly type: "Branch" | "Linear" | "Ending" | "Puzzle";
  readonly choices: number;
  readonly transitions: number;
  readonly validation: ValidationState;
  readonly lastUpdated: string;
}

export interface SceneEditorState {
  readonly sceneId: string;
  readonly sceneType: string;
  readonly sceneSummary: string;
  readonly statusMessage: string | null;
  readonly navigationLog: string;
  readonly activePrimaryTab: PrimaryTabId;
  readonly activeInspectorTab: InspectorTabId;
  readonly sampleSceneRows: SceneTableRow[];

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
}

const defaultSampleSceneRows: SceneTableRow[] = [
  {
    id: "mysterious-grove",
    title: "Mysterious Grove",
    type: "Branch",
    choices: 3,
    transitions: 4,
    validation: "clean",
    lastUpdated: "2 minutes ago",
  },
  {
    id: "shrouded-altar",
    title: "Shrouded Altar",
    type: "Puzzle",
    choices: 2,
    transitions: 3,
    validation: "warnings",
    lastUpdated: "12 minutes ago",
  },
  {
    id: "lunar-eclipse",
    title: "Lunar Eclipse",
    type: "Ending",
    choices: 1,
    transitions: 1,
    validation: "errors",
    lastUpdated: "27 minutes ago",
  },
];

const resetStatus = () => ({ statusMessage: null as string | null });

export const useSceneEditorStore = create<SceneEditorState>((set) => ({
  sceneId: "mysterious-grove",
  sceneType: "branch",
  sceneSummary: "A moonlit clearing reveals a hidden ritual site.",
  statusMessage: null,
  navigationLog:
    "Primary navigation focused on scene metadata and narrative notes.",
  activePrimaryTab: "details",
  activeInspectorTab: "overview",
  sampleSceneRows: defaultSampleSceneRows,
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
}));

export type { ValidationState };
