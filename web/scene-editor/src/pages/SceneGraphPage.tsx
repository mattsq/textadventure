import React from "react";
import ReactFlow, {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  type Edge,
  type Node,
  type ReactFlowInstance,
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
import { SceneGraphNode, type SceneGraphNodeData } from "../components/graph";
import type { AsyncStatus } from "../state";

interface SceneGraphEdgeData {
  readonly command: string;
  readonly narration: string;
  readonly isTerminal: boolean;
  readonly item?: string | null;
  readonly requires: readonly string[];
  readonly consumes: readonly string[];
  readonly records: readonly string[];
  readonly failureNarration?: string | null;
  readonly overrideCount: number;
}

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

  const unreachableScenes = nodes.length - visited.size;

  return { levelEntries, levelBySceneId, terminals, unreachableScenes };
};

const buildGraphView = (
  response: SceneGraphResponse,
): GraphViewModel => {
  const { levelEntries, levelBySceneId, terminals, unreachableScenes } =
    toLevelEntries(response.nodes, response.edges, response.start_scene);

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
      validationStatus: node.validation_status,
      choiceCount: node.choice_count,
      transitionCount: node.transition_count,
      hasTerminalTransition: node.has_terminal_transition,
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
    const target = isTerminal ? terminalNodeId(edge.id) : edge.target!;
    return {
      id: edge.id,
      source: edge.source,
      target,
      type: "smoothstep",
      label: edge.command,
      labelStyle: {
        fill: "#e2e8f0",
        fontSize: 12,
        textTransform: "uppercase",
      },
      labelBgPadding: [6, 3],
      labelBgBorderRadius: 12,
      labelBgStyle: {
        fill: "rgba(15, 23, 42, 0.8)",
        stroke: "rgba(148, 163, 184, 0.6)",
      },
      style: {
        stroke: isTerminal ? "#fb7185" : "#94a3b8",
        strokeWidth: 2,
      },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: isTerminal ? "#fb7185" : "#94a3b8",
        width: 16,
        height: 16,
      },
      animated: isTerminal,
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
  const legendItems = [
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
    {
      id: "terminal-edge",
      label: "Terminal transition",
      description: "Ends the adventure from this branch.",
      swatch: "bg-rose-500",
    },
  ];

  return (
    <div className="grid gap-3 md:grid-cols-2">
      {legendItems.map((item) => (
        <div
          key={item.id}
          className="flex items-start gap-3 rounded-lg border border-slate-800/80 bg-slate-900/40 p-3"
        >
          <span
            className={`mt-1 h-3.5 w-3.5 rounded-full ${item.swatch}`}
            aria-hidden
          />
          <div className="space-y-1">
            <p className="text-sm font-semibold text-slate-100">{item.label}</p>
            <p className="text-xs leading-relaxed text-slate-300">
              {item.description}
            </p>
          </div>
        </div>
      ))}
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

  const [graphState, setGraphState] = React.useState<GraphState>({
    status: "idle",
    data: null,
    error: null,
  });
  const reactFlowInstanceRef = React.useRef<ReactFlowInstance | null>(null);

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

  const nodeTypes = React.useMemo(() => ({
    sceneGraphNode: SceneGraphNode,
  }), []);

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
          <div className="h-[620px] w-full overflow-hidden rounded-xl border border-slate-800/80 bg-slate-950/60">
            <ReactFlow
              nodes={graphState.data!.nodes}
              edges={graphState.data!.edges}
              nodeTypes={nodeTypes}
              fitView
              onInit={(instance) => {
                reactFlowInstanceRef.current = instance;
                instance.fitView({ padding: 0.25, includeHiddenNodes: true });
              }}
              minZoom={0.2}
              maxZoom={1.8}
              defaultEdgeOptions={{
                type: "smoothstep",
              }}
              elevateNodesOnSelect
              proOptions={{ hideAttribution: true }}
              className="!bg-gradient-to-b !from-slate-950 !to-slate-900"
            >
              <Background color="#1f2937" gap={24} />
              <MiniMap
                pannable
                zoomable
                nodeColor={(node) =>
                  node.data.variant === "terminal" ? "#fb7185" : "#38bdf8"
                }
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
