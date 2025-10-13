import React from "react";
import { useNavigate } from "react-router-dom";
import ReactFlow, {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  type Edge,
  type Node,
  type ReactFlowInstance,
  type XYPosition,
  useEdgesState,
  useNodesState,
} from "reactflow";
import "reactflow/dist/style.css";

import {
  SceneEditorApiError,
  createSceneEditorApiClient,
  type SceneGraphEdgeResource,
  type SceneGraphNodeResource,
  type SceneGraphParams,
  type SceneGraphResponse,
} from "../api";
import { EditorPanel } from "../components/layout";
import { Card } from "../components/display";
import {
  SceneGraphEdge,
  type SceneGraphEdgeActivateContext,
  type SceneGraphEdgeData,
  type SceneGraphEdgeVariant,
  SceneGraphNode,
  type SceneGraphNodeData,
  type SceneGraphSceneType,
} from "../components/graph";
import type { AsyncStatus } from "../state";

interface EdgeStyleConfig {
  readonly stroke: string;
  readonly marker: string;
  readonly strokeDasharray?: string;
  readonly animated: boolean;
  readonly labelBgFill: string;
  readonly labelBgStroke: string;
  readonly labelTextColor: string;
}

const EDGE_VARIANT_STYLES: Record<SceneGraphEdgeVariant, EdgeStyleConfig> = {
  default: {
    stroke: "#94a3b8",
    marker: "#94a3b8",
    animated: false,
    labelBgFill: "rgba(15, 23, 42, 0.8)",
    labelBgStroke: "rgba(148, 163, 184, 0.6)",
    labelTextColor: "#e2e8f0",
  },
  conditional: {
    stroke: "#38bdf8",
    marker: "#38bdf8",
    strokeDasharray: "6 4",
    animated: false,
    labelBgFill: "rgba(12, 74, 110, 0.65)",
    labelBgStroke: "rgba(56, 189, 248, 0.7)",
    labelTextColor: "#e0f2fe",
  },
  consumable: {
    stroke: "#fbbf24",
    marker: "#fbbf24",
    strokeDasharray: "2 6",
    animated: false,
    labelBgFill: "rgba(120, 53, 15, 0.7)",
    labelBgStroke: "rgba(251, 191, 36, 0.6)",
    labelTextColor: "#fff7ed",
  },
  reward: {
    stroke: "#34d399",
    marker: "#34d399",
    animated: false,
    labelBgFill: "rgba(6, 47, 28, 0.7)",
    labelBgStroke: "rgba(52, 211, 153, 0.6)",
    labelTextColor: "#d1fae5",
  },
  terminal: {
    stroke: "#fb7185",
    marker: "#fb7185",
    animated: true,
    labelBgFill: "rgba(76, 29, 49, 0.75)",
    labelBgStroke: "rgba(251, 113, 133, 0.6)",
    labelTextColor: "#ffe4e6",
  },
};

interface TerminalNodeInfo {
  readonly id: string;
  readonly command: string;
  readonly narration: string;
  readonly level: number;
  readonly sourceScene: string;
}

interface GraphViewModel {
  readonly generatedAt: string;
  readonly startScene: string;
  readonly nodes: Node<SceneGraphNodeData>[];
  readonly edges: Edge<SceneGraphEdgeData>[];
  readonly stats: {
    readonly sceneCount: number;
    readonly terminalCount: number;
    readonly transitionCount: number;
    readonly unreachableCount: number;
  };
}

interface GraphState {
  readonly status: AsyncStatus;
  readonly data: GraphViewModel | null;
  readonly error: string | null;
}

const HORIZONTAL_SPACING = 320;
const VERTICAL_SPACING = 170;

type PathHighlightRole = "start" | "end" | "intermediate";

interface PathSelection {
  readonly startId: string;
  readonly targetId: string;
}

interface PathHighlightResult {
  readonly sceneIds: ReadonlySet<string>;
  readonly edgeIds: ReadonlySet<string>;
  readonly roles: ReadonlyMap<string, PathHighlightRole>;
  readonly isActive: boolean;
  readonly found: boolean;
  readonly length: number;
  readonly startId: string | null;
  readonly targetId: string | null;
  readonly missingStart: boolean;
  readonly missingTarget: boolean;
}

type PathStatusTone = "muted" | "info" | "warning" | "danger";

interface PathStatusMessage {
  readonly tone: PathStatusTone;
  readonly message: string;
}

const PATH_STATUS_TONE_CLASSES: Record<PathStatusTone, string> = {
  muted: "text-slate-400",
  info: "text-sky-200",
  warning: "text-amber-300",
  danger: "text-rose-300",
};

const computeScenePathHighlight = (
  graph: GraphViewModel | null,
  selection: PathSelection | null,
): PathHighlightResult => {
  if (!selection) {
    return {
      sceneIds: new Set<string>(),
      edgeIds: new Set<string>(),
      roles: new Map<string, PathHighlightRole>(),
      isActive: false,
      found: false,
      length: 0,
      startId: null,
      targetId: null,
      missingStart: false,
      missingTarget: false,
    };
  }

  if (!graph) {
    return {
      sceneIds: new Set<string>(),
      edgeIds: new Set<string>(),
      roles: new Map<string, PathHighlightRole>(),
      isActive: true,
      found: false,
      length: 0,
      startId: selection.startId,
      targetId: selection.targetId,
      missingStart: false,
      missingTarget: false,
    };
  }

  const sceneIds = new Set(
    graph.nodes
      .filter((node) => node.data.variant === "scene")
      .map((node) => node.id),
  );

  const missingStart = !sceneIds.has(selection.startId);
  const missingTarget = !sceneIds.has(selection.targetId);

  if (missingStart || missingTarget) {
    const highlightedScenes = new Set<string>();
    const roles = new Map<string, PathHighlightRole>();

    if (!missingStart) {
      highlightedScenes.add(selection.startId);
      roles.set(selection.startId, "start");
    }

    if (!missingTarget) {
      highlightedScenes.add(selection.targetId);
      roles.set(selection.targetId, "end");
    }

    return {
      sceneIds: highlightedScenes,
      edgeIds: new Set<string>(),
      roles,
      isActive: true,
      found: false,
      length: 0,
      startId: selection.startId,
      targetId: selection.targetId,
      missingStart,
      missingTarget,
    };
  }

  if (selection.startId === selection.targetId) {
    const singleScene = new Set<string>([selection.startId]);
    const roles = new Map<string, PathHighlightRole>([
      [selection.startId, "start"],
    ]);

    return {
      sceneIds: singleScene,
      edgeIds: new Set<string>(),
      roles,
      isActive: true,
      found: true,
      length: 0,
      startId: selection.startId,
      targetId: selection.targetId,
      missingStart: false,
      missingTarget: false,
    };
  }

  const adjacency = new Map<string, Array<{ edgeId: string; targetId: string }>>();

  for (const edge of graph.edges) {
    if (!edge.source || typeof edge.target !== "string") {
      continue;
    }

    if (edge.data?.isTerminal) {
      continue;
    }

    if (!sceneIds.has(edge.source) || !sceneIds.has(edge.target)) {
      continue;
    }

    if (!adjacency.has(edge.source)) {
      adjacency.set(edge.source, []);
    }

    adjacency.get(edge.source)!.push({ edgeId: edge.id, targetId: edge.target });
  }

  const visited = new Set<string>([selection.startId]);
  const parent = new Map<string, { prev: string; viaEdgeId: string }>();
  const queue: string[] = [selection.startId];
  let found = false;

  while (queue.length > 0) {
    const current = queue.shift()!;
    if (current === selection.targetId) {
      found = true;
      break;
    }

    const neighbors = adjacency.get(current) ?? [];
    for (const { edgeId, targetId } of neighbors) {
      if (visited.has(targetId)) {
        continue;
      }

      visited.add(targetId);
      parent.set(targetId, { prev: current, viaEdgeId: edgeId });

      if (targetId === selection.targetId) {
        found = true;
        queue.length = 0;
        break;
      }

      queue.push(targetId);
    }
  }

  if (!found) {
    return {
      sceneIds: new Set<string>([selection.startId, selection.targetId]),
      edgeIds: new Set<string>(),
      roles: new Map<string, PathHighlightRole>([
        [selection.startId, "start"],
        [selection.targetId, "end"],
      ]),
      isActive: true,
      found: false,
      length: 0,
      startId: selection.startId,
      targetId: selection.targetId,
      missingStart: false,
      missingTarget: false,
    };
  }

  const highlightedScenes = new Set<string>();
  const highlightedEdges = new Set<string>();
  let steps = 0;
  let cursor = selection.targetId;

  highlightedScenes.add(selection.targetId);

  while (cursor !== selection.startId) {
    const metadata = parent.get(cursor);
    if (!metadata) {
      break;
    }

    highlightedEdges.add(metadata.viaEdgeId);
    steps += 1;
    cursor = metadata.prev;
    highlightedScenes.add(cursor);
  }

  highlightedScenes.add(selection.startId);

  const roles = new Map<string, PathHighlightRole>();
  roles.set(selection.startId, "start");
  roles.set(selection.targetId, "end");

  for (const sceneId of highlightedScenes) {
    if (sceneId === selection.startId || sceneId === selection.targetId) {
      continue;
    }
    roles.set(sceneId, "intermediate");
  }

  return {
    sceneIds: highlightedScenes,
    edgeIds: highlightedEdges,
    roles,
    isActive: true,
    found: true,
    length: steps,
    startId: selection.startId,
    targetId: selection.targetId,
    missingStart: false,
    missingTarget: false,
  };
};

const terminalNodeId = (edgeId: string): string => `terminal:${edgeId}`;

const toLevelEntries = (
  nodes: readonly SceneGraphNodeResource[],
  edges: readonly SceneGraphEdgeResource[],
  startScene: string,
): {
  readonly levelEntries: Map<number, Array<{ id: string; variant: "scene" | "terminal" }>>;
  readonly levelBySceneId: Map<string, number>;
  readonly terminals: TerminalNodeInfo[];
  readonly unreachableScenes: number;
  readonly unreachableSceneIds: readonly string[];
} => {
  const adjacency = new Map<string, Set<string>>();
  for (const edge of edges) {
    if (!edge.target) {
      continue;
    }
    if (!adjacency.has(edge.source)) {
      adjacency.set(edge.source, new Set());
    }
    adjacency.get(edge.source)!.add(edge.target);
  }

  const levelBySceneId = new Map<string, number>();
  const visited = new Set<string>();
  const queue: Array<{ id: string; level: number }> = [];
  if (nodes.some((node) => node.id === startScene)) {
    queue.push({ id: startScene, level: 0 });
  }

  while (queue.length > 0) {
    const current = queue.shift()!;
    if (levelBySceneId.has(current.id)) {
      continue;
    }
    levelBySceneId.set(current.id, current.level);
    visited.add(current.id);

    const neighbors = adjacency.get(current.id);
    if (!neighbors) {
      continue;
    }
    for (const neighbor of neighbors) {
      if (!levelBySceneId.has(neighbor)) {
        queue.push({ id: neighbor, level: current.level + 1 });
      }
    }
  }

  let nextBaseLevel =
    levelBySceneId.size > 0
      ? Math.max(...levelBySceneId.values()) + 1
      : 0;
  const sortedSceneIds = [...nodes.map((node) => node.id)].sort((a, b) =>
    a.localeCompare(b),
  );

  for (const sceneId of sortedSceneIds) {
    if (levelBySceneId.has(sceneId)) {
      continue;
    }
    const localQueue: Array<{ id: string; level: number }> = [
      { id: sceneId, level: nextBaseLevel },
    ];
    nextBaseLevel += 1;

    while (localQueue.length > 0) {
      const entry = localQueue.shift()!;
      if (levelBySceneId.has(entry.id)) {
        continue;
      }
      levelBySceneId.set(entry.id, entry.level);
      const neighbors = adjacency.get(entry.id);
      if (!neighbors) {
        continue;
      }
      for (const neighbor of neighbors) {
        if (!levelBySceneId.has(neighbor)) {
          localQueue.push({ id: neighbor, level: entry.level + 1 });
        }
      }
    }
  }

  const levelEntries = new Map<
    number,
    Array<{ id: string; variant: "scene" | "terminal" }>
  >();

  for (const node of nodes) {
    const level = levelBySceneId.get(node.id) ?? 0;
    if (!levelEntries.has(level)) {
      levelEntries.set(level, []);
    }
    levelEntries.get(level)!.push({ id: node.id, variant: "scene" });
  }

  const terminals: TerminalNodeInfo[] = [];

  for (const edge of edges) {
    if (edge.target) {
      continue;
    }
    const sourceLevel = levelBySceneId.get(edge.source) ?? 0;
    const level = sourceLevel + 1;
    const id = terminalNodeId(edge.id);
    terminals.push({
      id,
      command: edge.command,
      narration: edge.narration,
      level,
      sourceScene: edge.source,
    });

    if (!levelEntries.has(level)) {
      levelEntries.set(level, []);
    }
    levelEntries.get(level)!.push({ id, variant: "terminal" });
  }

  for (const [, entries] of levelEntries) {
    entries.sort((a, b) => {
      if (a.variant === b.variant) {
        return a.id.localeCompare(b.id);
      }
      return a.variant === "scene" ? -1 : 1;
    });
  }

  const unreachableSceneIds: string[] = [];
  for (const node of nodes) {
    if (!visited.has(node.id)) {
      unreachableSceneIds.push(node.id);
    }
  }

  const unreachableScenes = unreachableSceneIds.length;

  return {
    levelEntries,
    levelBySceneId,
    terminals,
    unreachableScenes,
    unreachableSceneIds,
  };
};

const classifySceneType = (
  sceneId: string,
  startScene: string,
  edgesBySource: Map<string, SceneGraphEdgeResource[]>,
): SceneGraphSceneType => {
  if (sceneId === startScene) {
    return "start";
  }

  const edges = edgesBySource.get(sceneId) ?? [];
  let terminalCount = 0;
  let nonTerminalCount = 0;
  for (const edge of edges) {
    if (edge.is_terminal || edge.target === null) {
      terminalCount += 1;
    } else {
      nonTerminalCount += 1;
    }
  }

  if (nonTerminalCount === 0) {
    return "end";
  }

  if (nonTerminalCount > 1 || terminalCount > 0) {
    return "branch";
  }

  return "linear";
};

const buildGraphView = (
  response: SceneGraphResponse,
): GraphViewModel => {
  const {
    levelEntries,
    levelBySceneId,
    terminals,
    unreachableScenes,
    unreachableSceneIds,
  } = toLevelEntries(response.nodes, response.edges, response.start_scene);

  const unreachableSceneSet = new Set(unreachableSceneIds);

  const edgesBySource = new Map<string, SceneGraphEdgeResource[]>();
  for (const edge of response.edges) {
    if (!edgesBySource.has(edge.source)) {
      edgesBySource.set(edge.source, []);
    }
    edgesBySource.get(edge.source)!.push(edge);
  }

  const positions = new Map<string, { x: number; y: number }>();
  const orderedLevels = [...levelEntries.keys()].sort((a, b) => a - b);

  for (const level of orderedLevels) {
    const entries = levelEntries.get(level)!;
    const verticalOffset = (entries.length - 1) / 2;
    entries.forEach((entry, index) => {
      const y = (index - verticalOffset) * VERTICAL_SPACING;
      const x = level * HORIZONTAL_SPACING;
      positions.set(entry.id, { x, y });
    });
  }

  const nodes: Node<SceneGraphNodeData>[] = response.nodes.map((node) => ({
    id: node.id,
    type: "sceneGraphNode",
    position: positions.get(node.id) ?? { x: 0, y: 0 },
    data: {
      variant: "scene",
      id: node.id,
      label: node.id,
      description: node.description,
      sceneType: classifySceneType(
        node.id,
        response.start_scene,
        edgesBySource,
      ),
      validationStatus: node.validation_status,
      choiceCount: node.choice_count,
      transitionCount: node.transition_count,
      hasTerminalTransition: node.has_terminal_transition,
      isReachable: !unreachableSceneSet.has(node.id),
    },
    draggable: false,
  }));

  for (const terminal of terminals) {
    nodes.push({
      id: terminal.id,
      type: "sceneGraphNode",
      position: positions.get(terminal.id) ?? {
        x: terminal.level * HORIZONTAL_SPACING,
        y: 0,
      },
      data: {
        variant: "terminal",
        id: terminal.id,
        label: `Ending: ${terminal.command}`,
        command: terminal.command,
        narration: terminal.narration,
        sourceScene: terminal.sourceScene,
      },
      draggable: false,
    });
  }

  const edges: Edge<SceneGraphEdgeData>[] = response.edges.map((edge) => {
    const isTerminal = edge.target === null;
    const hasRequirements = edge.requires.length > 0;
    const consumesItems = edge.consumes.length > 0;
    const grantsReward = Boolean(edge.item) || edge.records.length > 0;
    const hasOverrides = edge.override_count > 0;
    let variant: SceneGraphEdgeVariant = "default";
    if (isTerminal) {
      variant = "terminal";
    } else if (consumesItems) {
      variant = "consumable";
    } else if (hasRequirements) {
      variant = "conditional";
    } else if (grantsReward || hasOverrides) {
      variant = "reward";
    }
    const styleConfig = EDGE_VARIANT_STYLES[variant];
    const target = isTerminal ? terminalNodeId(edge.id) : edge.target!;

    return {
      id: edge.id,
      source: edge.source,
      target,
      type: "sceneGraphEdge",
      style: {
        stroke: styleConfig.stroke,
        strokeWidth: 2,
        strokeDasharray: styleConfig.strokeDasharray,
      },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: styleConfig.marker,
        width: 16,
        height: 16,
      },
      animated: styleConfig.animated,
      data: {
        command: edge.command,
        narration: edge.narration,
        isTerminal,
        item: edge.item ?? null,
        requires: edge.requires,
        consumes: edge.consumes,
        records: edge.records,
        failureNarration: edge.failure_narration ?? null,
        overrideCount: edge.override_count,
        variant,
        hasRequirements,
        labelBackground: styleConfig.labelBgFill,
        labelBorder: styleConfig.labelBgStroke,
        labelTextColor: styleConfig.labelTextColor,
        sourceSceneId: edge.source,
      },
    };
  });

  return {
    generatedAt: response.generated_at,
    startScene: response.start_scene,
    nodes,
    edges,
    stats: {
      sceneCount: response.nodes.length,
      terminalCount: terminals.length,
      transitionCount: response.edges.length,
      unreachableCount: Math.max(unreachableScenes, 0),
    },
  };
};

const formatTimestamp = (value: string): string => {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
};

const GraphLegend: React.FC = () => {
  const validationLegendItems = [
    {
      id: "valid-scenes",
      label: "Validated scene",
      description: "No blocking issues detected.",
      swatch: "bg-emerald-400/80",
    },
    {
      id: "warning-scenes",
      label: "Scene with warnings",
      description: "Review validation hints before publishing.",
      swatch: "bg-amber-400/80",
    },
    {
      id: "error-scenes",
      label: "Scene with errors",
      description: "Requires fixes to pass validation.",
      swatch: "bg-rose-400/80",
    },
  ];

  const reachabilityLegendItems = [
    {
      id: "unreachable-scene",
      label: "Unreachable scene",
      description: "Not reachable from the configured start scene.",
      swatch: "bg-rose-500/80",
    },
  ];

  const sceneTypeLegendItems = [
    {
      id: "start-scene",
      label: "Start scene",
      description: "Entry point for the adventure graph.",
      swatch: "bg-sky-400/80",
    },
    {
      id: "end-scene",
      label: "Ending scene",
      description: "Leads exclusively to endings or has no exits.",
      swatch: "bg-rose-400/80",
    },
    {
      id: "branch-scene",
      label: "Branching scene",
      description: "Multiple possible destinations or endings.",
      swatch: "bg-violet-400/80",
    },
    {
      id: "linear-scene",
      label: "Linear scene",
      description: "Progresses to a single follow-up scene.",
      swatch: "bg-slate-300/80",
    },
  ];

  const edgeLegendItems = [
    {
      id: "default-edge",
      label: "Standard transition",
      description: "Moves between scenes without additional state effects.",
      swatch: "bg-slate-400",
    },
    {
      id: "conditional-edge",
      label: "Conditional transition",
      description: "Requires specific inventory or history before it can fire.",
      swatch: "bg-sky-500",
    },
    {
      id: "consumable-edge",
      label: "Consumable transition",
      description: "Consumes inventory items as part of the state change.",
      swatch: "bg-amber-400",
    },
    {
      id: "reward-edge",
      label: "Rewarding transition",
      description: "Grants items or records new memories when triggered.",
      swatch: "bg-emerald-400",
    },
    {
      id: "terminal-edge",
      label: "Terminal transition",
      description: "Ends the adventure from this branch.",
      swatch: "bg-rose-500",
    },
  ];

  const renderLegend = (
    title: string,
    items: typeof validationLegendItems,
    titleId: string,
  ): React.ReactNode => (
    <section aria-labelledby={titleId} className="space-y-3">
      <h3 id={titleId} className="text-sm font-semibold text-slate-200">
        {title}
      </h3>
      <div className="grid gap-3 md:grid-cols-2">
        {items.map((item) => (
          <div
            key={item.id}
            className="flex items-start gap-3 rounded-lg border border-slate-800/80 bg-slate-900/40 p-3"
          >
            <span
              className={`mt-1 h-3.5 w-3.5 rounded-full ${item.swatch}`}
              aria-hidden
            />
            <div className="space-y-1">
              <p className="text-sm font-semibold text-slate-100">
                {item.label}
              </p>
              <p className="text-xs leading-relaxed text-slate-300">
                {item.description}
              </p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );

  return (
    <div className="space-y-6">
      {renderLegend("Node validation", validationLegendItems, "legend-validation")}
      {renderLegend("Reachability", reachabilityLegendItems, "legend-reachability")}
      {renderLegend("Scene types", sceneTypeLegendItems, "legend-types")}
      {renderLegend("Transition styles", edgeLegendItems, "legend-edges")}
    </div>
  );
};

export const SceneGraphPage: React.FC = () => {
  const apiClient = React.useMemo(() => {
    const baseUrl =
      typeof import.meta.env.VITE_SCENE_API_BASE_URL === "string" &&
      import.meta.env.VITE_SCENE_API_BASE_URL.trim() !== ""
        ? import.meta.env.VITE_SCENE_API_BASE_URL
        : undefined;
    return createSceneEditorApiClient({ baseUrl });
  }, []);

  const navigate = useNavigate();

  const [graphState, setGraphState] = React.useState<GraphState>({
    status: "idle",
    data: null,
    error: null,
  });
  const reactFlowInstanceRef = React.useRef<ReactFlowInstance | null>(null);
  const initialLayoutRef = React.useRef<Map<string, XYPosition>>(new Map());
  const layoutOverridesRef = React.useRef<Map<string, XYPosition>>(new Map());
  const [nodes, setNodes, handleNodesChange] = useNodesState<SceneGraphNodeData>([]);
  const [edges, setEdges, handleEdgesChange] = useEdgesState<SceneGraphEdgeData>([]);
  const [isLayoutEditing, setIsLayoutEditing] = React.useState(false);
  const [interactionMode, setInteractionMode] = React.useState<"pan" | "select">("pan");
  const [isScrollZoomEnabled, setIsScrollZoomEnabled] = React.useState(true);
  const [sceneSearchTerm, setSceneSearchTerm] = React.useState("");
  const [sceneSearchError, setSceneSearchError] = React.useState<string | null>(null);
  const [focusedSceneId, setFocusedSceneId] = React.useState<string | null>(null);
  const [highlightedItemId, setHighlightedItemId] = React.useState("");
  const [pathStartSceneId, setPathStartSceneId] = React.useState("");
  const [pathTargetSceneId, setPathTargetSceneId] = React.useState("");
  const [pathSelection, setPathSelection] = React.useState<PathSelection | null>(null);
  const [pathFormError, setPathFormError] = React.useState<string | null>(null);

  const sceneIdOptions = React.useMemo(() => {
    return nodes
      .filter((node) => node.data.variant === "scene")
      .map((node) => node.data.id)
      .sort((a, b) => a.localeCompare(b));
  }, [nodes]);

  const availableItemOptions = React.useMemo(() => {
    if (!graphState.data) {
      return [] as string[];
    }

    const items = new Set<string>();
    for (const edge of graphState.data.edges) {
      const data = edge.data;
      if (!data) {
        continue;
      }

      if (data.item && data.item.trim() !== "") {
        items.add(data.item);
      }
      for (const requirement of data.requires) {
        if (requirement.trim() !== "") {
          items.add(requirement);
        }
      }
      for (const consumption of data.consumes) {
        if (consumption.trim() !== "") {
          items.add(consumption);
        }
      }
    }

    return Array.from(items).sort((a, b) => a.localeCompare(b));
  }, [graphState.data]);

  const normalisedHighlightedItem = React.useMemo(
    () => highlightedItemId.trim().toLowerCase(),
    [highlightedItemId],
  );

  const highlightedItemFlow = React.useMemo(() => {
    if (!graphState.data || normalisedHighlightedItem.length === 0) {
      return {
        edgeIds: new Set<string>(),
        sceneIds: new Set<string>(),
        terminalIds: new Set<string>(),
      };
    }

    const edgeIds = new Set<string>();
    const sceneIds = new Set<string>();
    const terminalIds = new Set<string>();

    for (const edge of graphState.data.edges) {
      const data = edge.data;
      if (!data) {
        continue;
      }

      const matchesItem =
        (data.item?.toLowerCase() ?? "") === normalisedHighlightedItem ||
        data.requires.some(
          (requirement) => requirement.toLowerCase() === normalisedHighlightedItem,
        ) ||
        data.consumes.some(
          (consumption) => consumption.toLowerCase() === normalisedHighlightedItem,
        );

      if (!matchesItem) {
        continue;
      }

      edgeIds.add(edge.id);
      if (edge.source) {
        sceneIds.add(edge.source);
      }

      if (data.isTerminal) {
        if (typeof edge.target === "string") {
          terminalIds.add(edge.target);
        }
      } else if (typeof edge.target === "string") {
        sceneIds.add(edge.target);
      }
    }

    return { edgeIds, sceneIds, terminalIds };
  }, [graphState.data, normalisedHighlightedItem]);

  const hasItemHighlightMatches = React.useMemo(() => {
    return (
      highlightedItemFlow.edgeIds.size > 0 ||
      highlightedItemFlow.sceneIds.size > 0 ||
      highlightedItemFlow.terminalIds.size > 0
    );
  }, [highlightedItemFlow]);

  const pathHighlight = React.useMemo(
    () => computeScenePathHighlight(graphState.data, pathSelection),
    [graphState.data, pathSelection],
  );

  const pathStatus = React.useMemo<PathStatusMessage>(() => {
    if (!pathSelection) {
      return {
        tone: "muted",
        message:
          "Select start and target scenes to highlight a traversal between them.",
      };
    }

    if (!graphState.data) {
      return {
        tone: "muted",
        message: "Load the scene graph to trace a path between scenes.",
      };
    }

    if (pathHighlight.missingStart && pathHighlight.missingTarget) {
      return {
        tone: "danger",
        message: `Scenes "${pathSelection.startId}" and "${pathSelection.targetId}" are not present in the current dataset.`,
      };
    }

    if (pathHighlight.missingStart) {
      return {
        tone: "danger",
        message: `Scene "${pathSelection.startId}" is not present in the current dataset.`,
      };
    }

    if (pathHighlight.missingTarget) {
      return {
        tone: "danger",
        message: `Scene "${pathSelection.targetId}" is not present in the current dataset.`,
      };
    }

    if (!pathHighlight.found) {
      return {
        tone: "warning",
        message: `No path found from "${pathSelection.startId}" to "${pathSelection.targetId}".`,
      };
    }

    if (pathSelection.startId === pathSelection.targetId) {
      return {
        tone: "info",
        message: `Start and target scenes match; highlighting "${pathSelection.startId}".`,
      };
    }

    const transitionLabel =
      pathHighlight.length === 1 ? "1 transition" : `${pathHighlight.length} transitions`;

    return {
      tone: "info",
      message: `Path from "${pathSelection.startId}" to "${pathSelection.targetId}" contains ${transitionLabel}.`,
    };
  }, [graphState.data, pathHighlight, pathSelection]);

  const handleSceneSearchInputChange = React.useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      setSceneSearchTerm(event.target.value);
      setSceneSearchError(null);
    },
    [],
  );

  const focusSceneById = React.useCallback(
    (rawSceneId: string): string | null => {
      const instance = reactFlowInstanceRef.current;
      if (!instance) {
        return null;
      }

      const normalised = rawSceneId.trim().toLowerCase();
      const targetNode = nodes.find(
        (node) =>
          node.data.variant === "scene" &&
          node.id.toLowerCase() === normalised,
      );

      if (!targetNode) {
        return null;
      }

      setFocusedSceneId(targetNode.id);
      instance.fitView({
        nodes: [{ id: targetNode.id }],
        padding: 0.6,
        duration: 400,
        includeHiddenNodes: true,
      });

      return targetNode.id;
    },
    [nodes],
  );

  const handleSceneSearchSubmit = React.useCallback(
    (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      const trimmed = sceneSearchTerm.trim();

      if (trimmed.length === 0) {
        setSceneSearchError("Enter a scene id to focus");
        setFocusedSceneId(null);
        return;
      }

      const matchedId = focusSceneById(trimmed);
      if (!matchedId) {
        setSceneSearchError("No scene found with that id");
        return;
      }

      setSceneSearchError(null);
      setSceneSearchTerm(matchedId);
    },
    [focusSceneById, sceneSearchTerm],
  );

  const handlePathStartChange = React.useCallback(
    (event: React.ChangeEvent<HTMLSelectElement>) => {
      setPathStartSceneId(event.target.value);
      setPathFormError(null);
    },
    [],
  );

  const handlePathTargetChange = React.useCallback(
    (event: React.ChangeEvent<HTMLSelectElement>) => {
      setPathTargetSceneId(event.target.value);
      setPathFormError(null);
    },
    [],
  );

  const handleTracePathSubmit = React.useCallback(
    (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();

      if (!graphState.data) {
        setPathFormError("Load the scene graph before tracing a path.");
        return;
      }

      if (pathStartSceneId.trim().length === 0 || pathTargetSceneId.trim().length === 0) {
        setPathFormError("Select both start and target scenes.");
        return;
      }

      if (
        !sceneIdOptions.includes(pathStartSceneId) ||
        !sceneIdOptions.includes(pathTargetSceneId)
      ) {
        setPathFormError("Selected scenes are not available in the current graph.");
        return;
      }

      setPathFormError(null);
      setPathSelection({ startId: pathStartSceneId, targetId: pathTargetSceneId });
    },
    [graphState.data, pathStartSceneId, pathTargetSceneId, sceneIdOptions],
  );

  const handleClearPath = React.useCallback(() => {
    setPathSelection(null);
    setPathStartSceneId("");
    setPathTargetSceneId("");
    setPathFormError(null);
  }, []);

  const handleClearSceneFocus = React.useCallback(() => {
    setSceneSearchTerm("");
    setSceneSearchError(null);
    setFocusedSceneId(null);
    const instance = reactFlowInstanceRef.current;
    if (instance) {
      instance.fitView({
        padding: 0.25,
        includeHiddenNodes: true,
        duration: 400,
      });
    }
  }, []);

  const handleItemHighlightChange = React.useCallback(
    (event: React.ChangeEvent<HTMLSelectElement>) => {
      setHighlightedItemId(event.target.value);
    },
    [],
  );

  const handleClearItemHighlight = React.useCallback(() => {
    setHighlightedItemId("");
  }, []);

  const handleSceneOpen = React.useCallback(
    (sceneId: string) => {
      navigate(`/scenes/${encodeURIComponent(sceneId)}`);
    },
    [navigate],
  );

  const handleTransitionOpen = React.useCallback(
    ({ sceneId, command }: SceneGraphEdgeActivateContext) => {
      if (!sceneId) {
        return;
      }

      const params = new URLSearchParams();
      const normalisedCommand = command.trim();
      if (normalisedCommand.length > 0) {
        params.set("transition", normalisedCommand);
      }

      const search = params.toString();
      navigate({
        pathname: `/scenes/${encodeURIComponent(sceneId)}`,
        search: search ? `?${search}` : "",
      });
    },
    [navigate],
  );

  const loadGraph = React.useCallback(
    (params?: SceneGraphParams, signal?: AbortSignal) => {
      setGraphState((previous) => ({
        status: "loading",
        data: previous.data,
        error: null,
      }));

      void apiClient
        .getSceneGraph(params ?? {}, { signal })
        .then((response) => {
          layoutOverridesRef.current = new Map();
          setGraphState({
            status: "success",
            data: buildGraphView(response),
            error: null,
          });
        })
        .catch((error: unknown) => {
          if (error instanceof DOMException && error.name === "AbortError") {
            return;
          }
          if (error instanceof SceneEditorApiError) {
            setGraphState({ status: "error", data: null, error: error.message });
            return;
          }
          setGraphState({
            status: "error",
            data: null,
            error:
              error instanceof Error
                ? error.message
                : "Unable to load the scene graph. Please try again.",
          });
        });
    },
    [apiClient],
  );

  React.useEffect(() => {
    const abortController = new AbortController();
    loadGraph({}, abortController.signal);
    return () => {
      abortController.abort();
    };
  }, [loadGraph]);

  React.useEffect(() => {
    if (graphState.status !== "success") {
      return;
    }
    const instance = reactFlowInstanceRef.current;
    if (!instance) {
      return;
    }
    const handle = window.requestAnimationFrame(() => {
      instance.fitView({ padding: 0.25, includeHiddenNodes: true, duration: 400 });
    });
    return () => {
      window.cancelAnimationFrame(handle);
    };
  }, [graphState.status]);

  React.useEffect(() => {
    if (!graphState.data) {
      setNodes([]);
      setEdges([]);
      initialLayoutRef.current = new Map();
      layoutOverridesRef.current = new Map();
      return;
    }

    initialLayoutRef.current = new Map(
      graphState.data.nodes.map((node) => [node.id, { ...node.position }]),
    );

    const highlightedSceneIds = highlightedItemFlow.sceneIds;
    const highlightedTerminalIds = highlightedItemFlow.terminalIds;
    const highlightedEdgeIds = highlightedItemFlow.edgeIds;
    const pathSceneIds = pathHighlight.sceneIds;
    const pathEdgeIds = pathHighlight.edgeIds;
    const pathRoles = pathHighlight.roles;
    const shouldDimItem =
      normalisedHighlightedItem.length > 0 && hasItemHighlightMatches;
    const shouldDimPath = pathHighlight.isActive && pathHighlight.found;
    const shouldDimUnmatched = shouldDimItem || shouldDimPath;

    setNodes((previousNodes) => {
      const previousPositions = new Map(
        previousNodes.map((node) => [node.id, { ...node.position }]),
      );

      return graphState.data!.nodes.map((node) => {
        const overridePosition = layoutOverridesRef.current.get(node.id);
        const previousPosition = previousPositions.get(node.id);
        const position =
          overridePosition ?? previousPosition ?? { ...node.position };

        if (node.data.variant === "scene") {
          const pathRole = pathRoles.get(node.id);
          const isSceneHighlighted =
            node.id === focusedSceneId ||
            highlightedSceneIds.has(node.id) ||
            pathSceneIds.has(node.id);
          return {
            ...node,
            position,
            data: {
              ...node.data,
              onOpen: handleSceneOpen,
              isHighlighted: isSceneHighlighted,
              isDimmed: shouldDimUnmatched && !isSceneHighlighted,
              pathHighlightRole: pathRole,
            },
          };
        }

        const isTerminalHighlighted =
          node.data.sourceScene === focusedSceneId ||
          highlightedTerminalIds.has(node.id);

        return {
          ...node,
          position,
          data: {
            ...node.data,
            isHighlighted: isTerminalHighlighted,
            isDimmed: shouldDimUnmatched && !isTerminalHighlighted,
          },
        };
      });
    });

    setEdges(
      graphState.data.edges.map((edge) => {
        if (!edge.data) {
          return edge;
        }

        const isPathEdge = pathEdgeIds.has(edge.id);
        const isHighlightedEdge = highlightedEdgeIds.has(edge.id) || isPathEdge;
        const isEdgeDimmed = shouldDimUnmatched && !isHighlightedEdge;

        return {
          ...edge,
          selected: isHighlightedEdge,
          style: {
            ...edge.style,
            opacity: isEdgeDimmed ? 0.35 : 1,
          },
          data: {
            ...edge.data,
            isDimmed: isEdgeDimmed,
            onOpen: (context) => {
              handleTransitionOpen({
                edgeId: context.edgeId,
                sceneId: edge.data?.sourceSceneId ?? edge.source,
                command: edge.data?.command ?? "",
              });
            },
          },
        };
      }),
    );
  }, [
    focusedSceneId,
    graphState.data,
    handleSceneOpen,
    handleTransitionOpen,
    hasItemHighlightMatches,
    highlightedItemFlow,
    normalisedHighlightedItem,
    pathHighlight,
    setEdges,
    setNodes,
  ]);

  React.useEffect(() => {
    setNodes((currentNodes) =>
      currentNodes.map((node) => {
        if (node.data.variant !== "scene") {
          return { ...node, draggable: false, selectable: false };
        }

        return {
          ...node,
          draggable: isLayoutEditing,
          selectable: isLayoutEditing,
        };
      }),
    );
  }, [isLayoutEditing, setNodes]);

  const handleNodeDragStop = React.useCallback(
    (_event: React.MouseEvent, node: Node<SceneGraphNodeData>) => {
      layoutOverridesRef.current.set(node.id, { ...node.position });
    },
    [],
  );

  const handleResetLayout = React.useCallback(() => {
    layoutOverridesRef.current = new Map(initialLayoutRef.current);
    setNodes((currentNodes) =>
      currentNodes.map((node) => {
        const position = initialLayoutRef.current.get(node.id);
        if (!position) {
          return node;
        }
        return {
          ...node,
          position: { ...position },
        };
      }),
    );

    const instance = reactFlowInstanceRef.current;
    if (instance) {
      instance.fitView({ padding: 0.25, includeHiddenNodes: true, duration: 400 });
    }
  }, [setNodes]);

  const handleZoomIn = React.useCallback(() => {
    const instance = reactFlowInstanceRef.current;
    if (instance) {
      instance.zoomIn({ duration: 200 });
    }
  }, []);

  const handleZoomOut = React.useCallback(() => {
    const instance = reactFlowInstanceRef.current;
    if (instance) {
      instance.zoomOut({ duration: 200 });
    }
  }, []);

  const handleFitView = React.useCallback(() => {
    const instance = reactFlowInstanceRef.current;
    if (instance) {
      instance.fitView({ padding: 0.25, includeHiddenNodes: true, duration: 400 });
    }
  }, []);

  const handleSetInteractionMode = React.useCallback((mode: "pan" | "select") => {
    setInteractionMode(mode);
  }, []);

  const toggleScrollZoom = React.useCallback(() => {
    setIsScrollZoomEnabled((previous) => !previous);
  }, []);

  const toggleLayoutEditing = React.useCallback(() => {
    setIsLayoutEditing((previous) => !previous);
  }, []);

  const nodeTypes = React.useMemo(() => ({
    sceneGraphNode: SceneGraphNode,
  }), []);

  const edgeTypes = React.useMemo(
    () => ({
      sceneGraphEdge: SceneGraphEdge,
    }),
    [],
  );

  const handleEdgeClick = React.useCallback(
    (_event: React.MouseEvent, edge: Edge<SceneGraphEdgeData>) => {
      const sceneId = edge.data?.sourceSceneId ?? edge.source ?? "";
      if (!sceneId) {
        return;
      }

      handleTransitionOpen({
        edgeId: edge.id,
        sceneId,
        command: edge.data?.command ?? "",
      });
    },
    [handleTransitionOpen],
  );

  const isLoading = graphState.status === "loading";
  const hasError = graphState.status === "error";
  const hasData = graphState.data !== null;

  const handleRefresh = () => {
    loadGraph();
  };

  const graphStats = graphState.data?.stats;
  const generatedAt = graphState.data?.generatedAt;

  return (
    <div className="space-y-6">
      <EditorPanel
        title="Scene Graph"
        description={
          <span>
            Visualise how scenes connect through player choices. This graph will
            evolve as validation and collaboration features come online.
          </span>
        }
        actions={
          <button
            type="button"
            onClick={handleRefresh}
            disabled={isLoading}
            className="inline-flex items-center gap-2 rounded-md border border-indigo-400/70 bg-indigo-500/20 px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-indigo-100 transition hover:bg-indigo-500/30 disabled:cursor-not-allowed disabled:border-slate-700 disabled:bg-slate-800/80 disabled:text-slate-400"
          >
            {isLoading ? (
              <span className="flex items-center gap-1">
                <span
                  className="h-2.5 w-2.5 animate-spin rounded-full border-2 border-indigo-200 border-t-transparent"
                  aria-hidden
                />
                Refreshing…
              </span>
            ) : (
              "Refresh graph"
            )}
          </button>
        }
        footer={
          generatedAt ? (
            <span>
              Last generated <span className="font-semibold">{formatTimestamp(generatedAt)}</span> from
              start scene <span className="font-semibold">{graphState.data?.startScene}</span>.
            </span>
          ) : (
            "Graph data is derived from the live scripted adventure dataset."
          )
        }
      >
        {hasError ? (
          <div className="rounded-lg border border-rose-500/60 bg-rose-500/10 p-4 text-sm text-rose-100">
            <p className="font-semibold">Unable to load the scene graph.</p>
            <p className="mt-1 text-xs text-rose-200/80">{graphState.error}</p>
            <button
              type="button"
              onClick={handleRefresh}
              className="mt-3 inline-flex items-center gap-2 rounded-md border border-rose-400/70 bg-rose-500/20 px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-rose-50 transition hover:bg-rose-500/30"
            >
              Try again
            </button>
          </div>
        ) : null}

        {graphStats ? (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <Card
              compact
              variant="subtle"
              title="Scenes"
              description="Total nodes represented in the graph"
            >
              <p className="text-2xl font-semibold text-slate-50">
                {graphStats.sceneCount}
              </p>
            </Card>
            <Card
              compact
              variant="subtle"
              title="Transitions"
              description="Edges connecting player choices"
            >
              <p className="text-2xl font-semibold text-slate-50">
                {graphStats.transitionCount}
              </p>
            </Card>
            <Card
              compact
              variant="subtle"
              title="Terminal branches"
              description="Transitions that end the adventure"
            >
              <p className="text-2xl font-semibold text-slate-50">
                {graphStats.terminalCount}
              </p>
            </Card>
            <Card
              compact
              variant="subtle"
              title="Unreachable scenes"
              description="Scenes not reachable from the configured start"
            >
              <p className="text-2xl font-semibold text-slate-50">
                {graphStats.unreachableCount}
              </p>
            </Card>
          </div>
        ) : null}

        {hasData ? (
          <div className="relative h-[620px] w-full overflow-hidden rounded-xl border border-slate-800/80 bg-slate-950/60">
            <div className="pointer-events-none absolute left-4 top-4 z-10 flex flex-col gap-2">
              <div className="pointer-events-auto rounded-lg border border-slate-700/80 bg-slate-900/80 p-3 shadow-lg shadow-slate-950/40">
                <div className="space-y-4">
                  <form
                    className="space-y-2"
                    onSubmit={handleSceneSearchSubmit}
                  >
                    <label
                      htmlFor="scene-graph-scene-search"
                      className="text-[11px] font-semibold uppercase tracking-wide text-slate-300"
                    >
                      Focus on scene
                    </label>
                    <div className="flex flex-wrap items-center gap-2">
                      <input
                        id="scene-graph-scene-search"
                        list="scene-graph-scene-ids"
                        type="text"
                        value={sceneSearchTerm}
                        onChange={handleSceneSearchInputChange}
                        placeholder="Search by scene id"
                        className="w-40 flex-1 rounded-md border border-slate-600/80 bg-slate-950/70 px-2 py-1 text-[11px] text-slate-100 placeholder:text-slate-500 focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400/60"
                        autoComplete="off"
                      />
                      <button
                        type="submit"
                        className="inline-flex items-center justify-center rounded-md border border-indigo-500/70 bg-indigo-500/20 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-indigo-100 transition hover:bg-indigo-500/30"
                      >
                        Focus
                      </button>
                      {focusedSceneId ? (
                        <button
                          type="button"
                          onClick={handleClearSceneFocus}
                          className="inline-flex items-center justify-center rounded-md border border-slate-600/80 bg-slate-800/80 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-100 transition hover:bg-slate-700/80"
                        >
                          Clear
                        </button>
                      ) : null}
                    </div>
                    <datalist id="scene-graph-scene-ids">
                      {sceneIdOptions.map((sceneId) => (
                        <option key={sceneId} value={sceneId} />
                      ))}
                    </datalist>
                    {sceneSearchError ? (
                      <p className="text-[10px] font-medium text-rose-300">
                        {sceneSearchError}
                      </p>
                    ) : (
                      <p className="text-[10px] text-slate-400">
                        Start typing a scene id to highlight it in the graph.
                      </p>
                    )}
                  </form>
                  <form className="space-y-2" onSubmit={handleTracePathSubmit}>
                    <label
                      htmlFor="scene-graph-path-start"
                      className="text-[11px] font-semibold uppercase tracking-wide text-slate-300"
                    >
                      Trace path between scenes
                    </label>
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] uppercase tracking-wide text-slate-400">
                          From
                        </span>
                        <select
                          id="scene-graph-path-start"
                          value={pathStartSceneId}
                          onChange={handlePathStartChange}
                          className="w-full rounded-md border border-slate-600/80 bg-slate-950/70 px-2 py-1.5 text-[11px] text-slate-100 focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400/60"
                          disabled={!graphState.data}
                        >
                          <option value="">Select scene</option>
                          {sceneIdOptions.map((sceneId) => (
                            <option key={`path-start-${sceneId}`} value={sceneId}>
                              {sceneId}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] uppercase tracking-wide text-slate-400">
                          To
                        </span>
                        <select
                          id="scene-graph-path-target"
                          value={pathTargetSceneId}
                          onChange={handlePathTargetChange}
                          className="w-full rounded-md border border-slate-600/80 bg-slate-950/70 px-2 py-1.5 text-[11px] text-slate-100 focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400/60"
                          disabled={!graphState.data}
                        >
                          <option value="">Select scene</option>
                          {sceneIdOptions.map((sceneId) => (
                            <option key={`path-target-${sceneId}`} value={sceneId}>
                              {sceneId}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <button
                          type="submit"
                          className="inline-flex items-center justify-center rounded-md border border-emerald-500/70 bg-emerald-500/20 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-emerald-100 transition hover:bg-emerald-500/30 disabled:cursor-not-allowed disabled:border-slate-700 disabled:bg-slate-800/60 disabled:text-slate-400"
                          disabled={!graphState.data}
                        >
                          Trace path
                        </button>
                        {pathSelection ? (
                          <button
                            type="button"
                            onClick={handleClearPath}
                            className="inline-flex items-center justify-center rounded-md border border-slate-600/80 bg-slate-800/80 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-100 transition hover:bg-slate-700/80"
                          >
                            Clear
                          </button>
                        ) : null}
                      </div>
                    </div>
                    {pathFormError ? (
                      <p className="text-[10px] font-medium text-rose-300">{pathFormError}</p>
                    ) : (
                      <p
                        className={`text-[10px] ${PATH_STATUS_TONE_CLASSES[pathStatus.tone]}`}
                      >
                        {pathStatus.message}
                      </p>
                    )}
                  </form>
                  <div>
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-300">
                        View controls
                      </p>
                      <span className="text-[10px] uppercase tracking-wide text-slate-500">
                        {interactionMode === "pan" ? "Pan" : "Select"} mode
                      </span>
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-2">
                      <button
                        type="button"
                        onClick={handleZoomIn}
                        className="inline-flex items-center justify-center rounded-md border border-slate-600/80 bg-slate-800/80 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-100 transition hover:bg-slate-700/80"
                      >
                        Zoom in
                      </button>
                      <button
                        type="button"
                        onClick={handleZoomOut}
                        className="inline-flex items-center justify-center rounded-md border border-slate-600/80 bg-slate-800/80 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-100 transition hover:bg-slate-700/80"
                      >
                        Zoom out
                      </button>
                      <button
                        type="button"
                        onClick={handleFitView}
                        className="inline-flex items-center justify-center rounded-md border border-indigo-500/70 bg-indigo-500/20 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-indigo-100 transition hover:bg-indigo-500/30"
                      >
                        Fit view
                      </button>
                      <button
                        type="button"
                        onClick={handleResetLayout}
                        className="inline-flex items-center justify-center rounded-md border border-emerald-500/70 bg-emerald-500/20 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-emerald-100 transition hover:bg-emerald-500/30"
                      >
                        Reset layout
                      </button>
                    </div>
                  <div className="mt-3 space-y-2 text-[11px] text-slate-300">
                    <div className="flex items-center justify-between gap-2">
                      <span className="uppercase tracking-wide text-slate-400">Scroll zoom</span>
                      <button
                        type="button"
                          onClick={toggleScrollZoom}
                          className="inline-flex items-center justify-center rounded-full border border-slate-500/70 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-100 transition hover:bg-slate-800/90"
                        >
                          {isScrollZoomEnabled ? "On" : "Off"}
                        </button>
                      </div>
                      <div className="flex items-center justify-between gap-2">
                        <span className="uppercase tracking-wide text-slate-400">Interaction</span>
                        <div className="inline-flex rounded-full border border-slate-600/80 bg-slate-800/80 p-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-100">
                          <button
                            type="button"
                            onClick={() => handleSetInteractionMode("pan")}
                            className={
                              interactionMode === "pan"
                                ? "rounded-full bg-slate-700/80 px-2 py-0.5"
                                : "rounded-full px-2 py-0.5 text-slate-400 hover:text-slate-100"
                            }
                          >
                            Pan
                          </button>
                          <button
                            type="button"
                            onClick={() => handleSetInteractionMode("select")}
                            className={
                              interactionMode === "select"
                                ? "rounded-full bg-slate-700/80 px-2 py-0.5"
                                : "rounded-full px-2 py-0.5 text-slate-400 hover:text-slate-100"
                            }
                          >
                            Select
                          </button>
                        </div>
                      </div>
                      <div className="flex items-center justify-between gap-2">
                        <span className="uppercase tracking-wide text-slate-400">Layout editing</span>
                        <button
                          type="button"
                          onClick={toggleLayoutEditing}
                          className="inline-flex items-center justify-center rounded-full border border-emerald-500/70 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-100 transition hover:bg-emerald-500/20"
                        >
                          {isLayoutEditing ? "Enabled" : "Disabled"}
                        </button>
                      </div>
                    </div>
                  </div>
                  <div>
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-300">
                        Item flow highlight
                      </p>
                      {normalisedHighlightedItem.length > 0 ? (
                        <button
                          type="button"
                          onClick={handleClearItemHighlight}
                          className="inline-flex items-center justify-center rounded-md border border-slate-600/80 bg-slate-800/80 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide text-slate-100 transition hover:bg-slate-700/80"
                        >
                          Clear
                        </button>
                      ) : null}
                    </div>
                    <div className="mt-3 space-y-2">
                      <select
                        value={highlightedItemId}
                        onChange={handleItemHighlightChange}
                        className="w-full rounded-md border border-slate-600/80 bg-slate-950/70 px-2 py-1.5 text-[11px] text-slate-100 focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400/60 disabled:cursor-not-allowed disabled:text-slate-500"
                        disabled={availableItemOptions.length === 0}
                      >
                        <option value="">No highlight</option>
                        {availableItemOptions.map((item) => (
                          <option key={item} value={item}>
                            {item}
                          </option>
                        ))}
                      </select>
                      {availableItemOptions.length === 0 ? (
                        <p className="text-[10px] text-slate-500">
                          Item metadata will appear once transitions grant, consume, or
                          require inventory entries.
                        </p>
                      ) : (
                        <p className="text-[10px] text-slate-400">
                          Highlight transitions and scenes that require, consume, or
                          grant the selected item.
                        </p>
                      )}
                      {normalisedHighlightedItem.length > 0 && !hasItemHighlightMatches ? (
                        <p className="text-[10px] font-medium text-amber-300">
                          No transitions currently reference this item.
                        </p>
                      ) : null}
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              edgeTypes={edgeTypes}
              fitView
              onInit={(instance) => {
                reactFlowInstanceRef.current = instance;
                instance.fitView({ padding: 0.25, includeHiddenNodes: true });
              }}
              minZoom={0.2}
              maxZoom={1.8}
              elevateNodesOnSelect
              proOptions={{ hideAttribution: true }}
              onEdgeClick={handleEdgeClick}
              onNodesChange={handleNodesChange}
              onEdgesChange={handleEdgesChange}
              onNodeDragStop={handleNodeDragStop}
              panOnDrag={interactionMode === "pan"}
              panOnScroll={interactionMode === "pan"}
              selectionOnDrag={interactionMode === "select"}
              zoomOnScroll={isScrollZoomEnabled}
              zoomOnPinch={isScrollZoomEnabled}
              className="!bg-gradient-to-b !from-slate-950 !to-slate-900"
            >
              <Background color="#1f2937" gap={24} />
              <MiniMap
                pannable
                zoomable
                nodeColor={(node) => {
                  if (node?.data?.variant === "terminal") {
                    return "#fb7185";
                  }
                  if (node?.data?.variant === "scene") {
                    if (!node.data.isReachable) {
                      return "#ef4444";
                    }

                    switch (node.data.validationStatus) {
                      case "valid":
                        return "#34d399";
                      case "warnings":
                        return "#fbbf24";
                      case "errors":
                        return "#f87171";
                      default:
                        return "#38bdf8";
                    }
                  }
                  return "#38bdf8";
                }}
                maskColor="rgba(15, 23, 42, 0.85)"
              />
              <Controls position="bottom-right" />
            </ReactFlow>
          </div>
        ) : null}

        {isLoading && !hasData ? (
          <div className="flex items-center justify-center rounded-lg border border-slate-800/80 bg-slate-900/40 p-16 text-sm text-slate-200">
            <span className="flex items-center gap-2">
              <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-indigo-200 border-t-transparent" />
              Loading scene graph…
            </span>
          </div>
        ) : null}

        <div className="space-y-3">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-300">
            Legend
          </h3>
          <GraphLegend />
          <p className="text-xs leading-relaxed text-slate-400">
            Scene coordinates are auto-laid out by distance from the configured start scene. Terminal
            nodes appear to the right of their origin scenes so you can quickly inspect branches that end
            the adventure.
          </p>
        </div>
      </EditorPanel>
    </div>
  );
};

export default SceneGraphPage;
