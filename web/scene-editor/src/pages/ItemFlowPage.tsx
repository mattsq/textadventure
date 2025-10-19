import React from "react";
import dagre from "@dagrejs/dagre";
import { useNavigate } from "react-router-dom";
import ReactFlow, {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  type Edge,
  type Node,
  type ReactFlowInstance,
  useEdgesState,
  useNodesState,
} from "reactflow";
import "reactflow/dist/style.css";

import {
  SceneEditorApiError,
  createSceneEditorApiClient,
  type ItemFlowDetailsResource,
  type ItemFlowSummaryResource,
  type SceneValidationReport,
  type SceneValidationResponse,
} from "../api";
import { EditorPanel } from "../components/layout";
import { Badge, Card } from "../components/display";
import { SelectField } from "../components/forms";
import {
  ItemFlowNode,
  type ItemFlowNodeData,
  type ItemFlowSceneRelation,
  type ItemFlowSceneNodeData,
} from "../components/graph";
import type { AsyncStatus } from "../state";

interface ItemFlowState {
  readonly status: AsyncStatus;
  readonly data: SceneValidationReport | null;
  readonly error: string | null;
}

type ItemFilterValue = "all" | string;

const ITEM_NODE_TYPE = "item-flow";

const nodeTypes = {
  [ITEM_NODE_TYPE]: ItemFlowNode,
} as const;

interface SceneReferenceInfo {
  readonly relationTypes: Set<ItemFlowSceneRelation>;
  referenceCount: number;
}

interface GraphBuildResult {
  readonly nodes: Node<ItemFlowNodeData>[];
  readonly edges: Edge[];
}

interface SceneItemSummary {
  readonly sceneId: string;
  readonly itemIds: readonly string[];
  readonly itemCount: number;
  readonly commandCount: number;
}

const ITEM_NODE_DIMENSIONS = { width: 280, height: 260 } as const;
const SCENE_NODE_DIMENSIONS = { width: 260, height: 220 } as const;

const DAGRE_LAYOUT_CONFIG = {
  rankdir: "LR",
  nodesep: 160,
  ranksep: 200,
  marginx: 120,
  marginy: 100,
} as const;

const edgeVariantStyles: Record<
  ItemFlowSceneRelation,
  {
    readonly stroke: string;
    readonly labelBgFill: string;
    readonly labelTextColor: string;
  }
> = {
  source: {
    stroke: "#34d399",
    labelBgFill: "rgba(6, 47, 28, 0.75)",
    labelTextColor: "#d1fae5",
  },
  requirement: {
    stroke: "#38bdf8",
    labelBgFill: "rgba(12, 74, 110, 0.75)",
    labelTextColor: "#e0f2fe",
  },
  consumption: {
    stroke: "#f87171",
    labelBgFill: "rgba(76, 29, 49, 0.75)",
    labelTextColor: "#ffe4e6",
  },
};

interface BuildItemFlowGraphOptions {
  readonly filterItem: ItemFilterValue;
  readonly onOpenScene: (sceneId: string) => void;
}

const buildItemFlowGraph = (
  itemFlow: ItemFlowSummaryResource,
  { filterItem, onOpenScene }: BuildItemFlowGraphOptions,
): GraphBuildResult => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setGraph({ ...DAGRE_LAYOUT_CONFIG });
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  const itemNodes = new Map<string, Node<ItemFlowNodeData>>();
  const sceneNodes = new Map<string, ItemFlowSceneNodeData>();
  const sceneReferences = new Map<string, SceneReferenceInfo>();
  const edges: Edge[] = [];

  const applicableItems =
    filterItem === "all"
      ? itemFlow.items
      : itemFlow.items.filter((detail) => detail.item === filterItem);

  const addSceneReference = (sceneId: string, relation: ItemFlowSceneRelation) => {
    let info = sceneReferences.get(sceneId);
    if (!info) {
      info = { relationTypes: new Set<ItemFlowSceneRelation>(), referenceCount: 0 };
      sceneReferences.set(sceneId, info);
    }
    info.relationTypes.add(relation);
    info.referenceCount += 1;
  };

  for (const detail of applicableItems) {
    const itemNodeId = `item:${detail.item}`;
    if (!itemNodes.has(itemNodeId)) {
      const itemNode: Node<ItemFlowNodeData> = {
        id: itemNodeId,
        type: ITEM_NODE_TYPE,
        position: { x: 0, y: 0 },
        data: {
          variant: "item",
          itemId: detail.item,
          sourceCount: detail.sources.length,
          requirementCount: detail.requirements.length,
          consumptionCount: detail.consumptions.length,
          isOrphaned: detail.is_orphaned,
          isMissingSource: detail.is_missing_source,
          hasSurplusAwards: detail.has_surplus_awards,
          hasConsumptionDeficit: detail.has_consumption_deficit,
        },
      };
      itemNodes.set(itemNodeId, itemNode);
      dagreGraph.setNode(itemNodeId, {
        width: ITEM_NODE_DIMENSIONS.width,
        height: ITEM_NODE_DIMENSIONS.height,
      });
    }

    detail.sources.forEach((reference, index) => {
      const sceneNodeId = `scene:${reference.scene_id}`;
      addSceneReference(reference.scene_id, "source");

      const edgeId = `source:${reference.scene_id}:${detail.item}:${index}`;
      const variant = edgeVariantStyles.source;
      edges.push({
        id: edgeId,
        source: sceneNodeId,
        target: itemNodeId,
        type: "smoothstep",
        label: reference.command,
        animated: false,
        style: { stroke: variant.stroke, strokeWidth: 2 },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: variant.stroke,
          width: 14,
          height: 14,
        },
        labelBgPadding: [8, 4],
        labelBgBorderRadius: 6,
        labelBgStyle: {
          fill: variant.labelBgFill,
          fillOpacity: 0.95,
        },
        labelStyle: {
          fill: variant.labelTextColor,
          fontSize: 12,
          fontWeight: 600,
        },
      });
    });

    detail.requirements.forEach((reference, index) => {
      const sceneNodeId = `scene:${reference.scene_id}`;
      addSceneReference(reference.scene_id, "requirement");

      const edgeId = `requirement:${detail.item}:${reference.scene_id}:${index}`;
      const variant = edgeVariantStyles.requirement;
      edges.push({
        id: edgeId,
        source: itemNodeId,
        target: sceneNodeId,
        type: "smoothstep",
        label: reference.command,
        animated: false,
        style: { stroke: variant.stroke, strokeWidth: 2 },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: variant.stroke,
          width: 14,
          height: 14,
        },
        labelBgPadding: [8, 4],
        labelBgBorderRadius: 6,
        labelBgStyle: {
          fill: variant.labelBgFill,
          fillOpacity: 0.95,
        },
        labelStyle: {
          fill: variant.labelTextColor,
          fontSize: 12,
          fontWeight: 600,
        },
      });
    });

    detail.consumptions.forEach((reference, index) => {
      const sceneNodeId = `scene:${reference.scene_id}`;
      addSceneReference(reference.scene_id, "consumption");

      const edgeId = `consumption:${detail.item}:${reference.scene_id}:${index}`;
      const variant = edgeVariantStyles.consumption;
      edges.push({
        id: edgeId,
        source: itemNodeId,
        target: sceneNodeId,
        type: "smoothstep",
        label: reference.command,
        animated: false,
        style: { stroke: variant.stroke, strokeWidth: 2, strokeDasharray: "6 3" },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: variant.stroke,
          width: 14,
          height: 14,
        },
        labelBgPadding: [8, 4],
        labelBgBorderRadius: 6,
        labelBgStyle: {
          fill: variant.labelBgFill,
          fillOpacity: 0.95,
        },
        labelStyle: {
          fill: variant.labelTextColor,
          fontSize: 12,
          fontWeight: 600,
        },
      });
    });
  }

  for (const [sceneId, info] of sceneReferences) {
    const sceneNodeId = `scene:${sceneId}`;
    if (!sceneNodes.has(sceneNodeId)) {
      const sceneNodeData: ItemFlowSceneNodeData = {
        variant: "scene",
        sceneId,
        relationTypes: [...info.relationTypes],
        referenceCount: info.referenceCount,
        onOpenScene,
      };
      sceneNodes.set(sceneNodeId, sceneNodeData);
      dagreGraph.setNode(sceneNodeId, {
        width: SCENE_NODE_DIMENSIONS.width,
        height: SCENE_NODE_DIMENSIONS.height,
      });
    }
  }

  const nodes: Node<ItemFlowNodeData>[] = [
    ...itemNodes.values(),
    ...Array.from(sceneNodes.entries()).map(([id, data]) => ({
      id,
      type: ITEM_NODE_TYPE,
      position: { x: 0, y: 0 },
      data,
    })),
  ];

  for (const edge of edges) {
    dagreGraph.setEdge(edge.source, edge.target);
  }

  dagre.layout(dagreGraph);

  const positionedNodes = nodes.map((node) => {
    const layoutNode = dagreGraph.node(node.id);
    if (!layoutNode) {
      return node;
    }

    const isItem = node.data.variant === "item";
    const width =
      typeof layoutNode.width === "number"
        ? layoutNode.width
        : isItem
          ? ITEM_NODE_DIMENSIONS.width
          : SCENE_NODE_DIMENSIONS.width;
    const height =
      typeof layoutNode.height === "number"
        ? layoutNode.height
        : isItem
          ? ITEM_NODE_DIMENSIONS.height
          : SCENE_NODE_DIMENSIONS.height;

    return {
      ...node,
      position: {
        x: layoutNode.x - width / 2,
        y: layoutNode.y - height / 2,
      },
    };
  });

  return { nodes: positionedNodes, edges };
};

type ItemFlowRelationKey = "sources" | "requirements" | "consumptions";

const summariseItemFlowByScene = (
  itemFlow: ItemFlowSummaryResource | null,
  relation: ItemFlowRelationKey,
): readonly SceneItemSummary[] => {
  if (!itemFlow) {
    return [];
  }

  const summaries = new Map<string, { items: Set<string>; commands: Set<string> }>();

  for (const detail of itemFlow.items) {
    const references = detail[relation];
    for (const reference of references) {
      let aggregate = summaries.get(reference.scene_id);
      if (!aggregate) {
        aggregate = { items: new Set<string>(), commands: new Set<string>() };
        summaries.set(reference.scene_id, aggregate);
      }
      aggregate.items.add(detail.item);
      aggregate.commands.add(reference.command);
    }
  }

  const results: SceneItemSummary[] = [];
  for (const [sceneId, aggregate] of summaries) {
    const sortedItems = Array.from(aggregate.items).sort((a, b) => a.localeCompare(b));
    results.push({
      sceneId,
      itemIds: sortedItems,
      itemCount: sortedItems.length,
      commandCount: aggregate.commands.size,
    });
  }

  results.sort((a, b) => {
    if (b.itemCount !== a.itemCount) {
      return b.itemCount - a.itemCount;
    }
    if (b.commandCount !== a.commandCount) {
      return b.commandCount - a.commandCount;
    }
    return a.sceneId.localeCompare(b.sceneId);
  });

  return results;
};

const formatCountLabel = (count: number, singular: string, plural: string): string =>
  `${count} ${count === 1 ? singular : plural}`;

const SOURCE_SUMMARY_LIMIT = 8;
const REQUIREMENT_SUMMARY_LIMIT = 8;

const formatTimestamp = (value: string | null): string => {
  if (!value) {
    return "Unknown";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
};

const buildItemOptions = (report: SceneValidationReport | null): readonly string[] => {
  if (!report) {
    return [];
  }
  const items = report.item_flow.items.map((detail) => detail.item);
  const unique = Array.from(new Set(items));
  unique.sort((a, b) => a.localeCompare(b));
  return unique;
};

const findItemDetail = (
  report: SceneValidationReport | null,
  itemId: string,
): ItemFlowDetailsResource | null => {
  if (!report) {
    return null;
  }
  return report.item_flow.items.find((detail) => detail.item === itemId) ?? null;
};

export const ItemFlowPage: React.FC = () => {
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

  const [state, setState] = React.useState<ItemFlowState>({
    status: "idle",
    data: null,
    error: null,
  });
  const [selectedItem, setSelectedItem] = React.useState<ItemFilterValue>("all");
  const [nodes, setNodes, onNodesChange] = useNodesState<ItemFlowNodeData>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [reactFlowInstance, setReactFlowInstance] = React.useState<ReactFlowInstance | null>(null);
  const handleOpenScene = React.useCallback(
    (sceneId: string) => {
      navigate(`/scenes/${encodeURIComponent(sceneId)}`);
    },
    [navigate],
  );

  React.useEffect(() => {
    const abortController = new AbortController();

    const fetchValidation = async () => {
      setState({ status: "loading", data: null, error: null });
      try {
        const response: SceneValidationResponse = await apiClient.validateScenes(
          {},
          { signal: abortController.signal },
        );
        setState({ status: "success", data: response.data, error: null });
      } catch (error) {
        if (abortController.signal.aborted) {
          return;
        }
        if (error instanceof SceneEditorApiError) {
          setState({
            status: "error",
            data: null,
            error: error.message,
          });
          return;
        }
        if (error instanceof Error) {
          setState({ status: "error", data: null, error: error.message });
        } else {
          setState({ status: "error", data: null, error: "Failed to load item flow." });
        }
      }
    };

    void fetchValidation();

    return () => {
      abortController.abort();
    };
  }, [apiClient]);

  const itemOptions = React.useMemo(() => buildItemOptions(state.data), [state.data]);

  React.useEffect(() => {
    if (!state.data) {
      setNodes([]);
      setEdges([]);
      return;
    }

    if (selectedItem !== "all" && !itemOptions.includes(selectedItem)) {
      setSelectedItem("all");
      return;
    }

    const { nodes: builtNodes, edges: builtEdges } = buildItemFlowGraph(state.data.item_flow, {
      filterItem: selectedItem,
      onOpenScene: handleOpenScene,
    });

    setNodes(builtNodes);
    setEdges(builtEdges);
  }, [state.data, selectedItem, itemOptions, setNodes, setEdges, handleOpenScene]);

  React.useEffect(() => {
    if (!reactFlowInstance) {
      return;
    }
    if (nodes.length === 0) {
      return;
    }
    const timeout = window.setTimeout(() => {
      reactFlowInstance.fitView({ padding: 0.2, duration: 400 });
    }, 50);
    return () => {
      window.clearTimeout(timeout);
    };
  }, [reactFlowInstance, nodes, edges]);

  const selectedItemDetail = React.useMemo(
    () => (selectedItem === "all" ? null : findItemDetail(state.data, selectedItem)),
    [state.data, selectedItem],
  );

  const totalItems = state.data?.item_flow.items.length ?? 0;
  const flaggedCounts = React.useMemo(
    () => ({
      orphaned: state.data?.item_flow.orphaned_items.length ?? 0,
      missingSources: state.data?.item_flow.items_missing_sources.length ?? 0,
      surplusAwards: state.data?.item_flow.items_with_surplus_awards.length ?? 0,
      consumptionDeficit: state.data?.item_flow.items_with_consumption_deficit.length ?? 0,
      unreachableSources: state.data?.item_flow.items_with_unreachable_sources.length ?? 0,
    }),
    [state.data],
  );
  const sourceSummaries = React.useMemo(
    () => summariseItemFlowByScene(state.data?.item_flow ?? null, "sources"),
    [state.data],
  );
  const requirementSummaries = React.useMemo(
    () => summariseItemFlowByScene(state.data?.item_flow ?? null, "requirements"),
    [state.data],
  );

  return (
    <div className="grid grid-cols-5 gap-6">
      <div className="col-span-5 xl:col-span-4 space-y-4">
        <Card>
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="text-lg font-semibold text-slate-100">Item dependency graph</h2>
              <Badge variant="info" size="sm">
                {totalItems} {totalItems === 1 ? "item" : "items"}
              </Badge>
              <span className="text-xs text-slate-400">
                Validation snapshot generated at {formatTimestamp(state.data?.generated_at ?? null)}
              </span>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <SelectField
                label="Focus on a specific item"
                value={selectedItem === "all" ? "all" : selectedItem}
                onChange={(event) => setSelectedItem(event.target.value as ItemFilterValue)}
                description="Choose an item to isolate its sources, requirements, and consumptions."
              >
                <option value="all">All items</option>
                {itemOptions.map((itemId) => (
                  <option key={itemId} value={itemId}>
                    {itemId}
                  </option>
                ))}
              </SelectField>
              <div className="rounded-lg border border-slate-700/60 bg-slate-900/60 p-3 text-xs leading-relaxed text-slate-300">
                {state.status === "loading" ? (
                  <p>Loading item flow from the validation service…</p>
                ) : state.status === "error" ? (
                  <p className="text-rose-300">{state.error ?? "Unable to load item flow data."}</p>
                ) : (
                  <p>
                    Hover nodes to review item statistics and use the graph controls to inspect how scenes award, require, or
                    consume each item.
                  </p>
                )}
              </div>
            </div>
          </div>
        </Card>

        <div className="relative h-[720px] overflow-hidden rounded-2xl border border-slate-700/60 bg-slate-950/70">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            nodesConnectable={false}
            elementsSelectable
            zoomOnScroll
            zoomOnPinch
            panOnDrag
            fitView
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onInit={setReactFlowInstance}
          >
            <Background gap={24} color="#1e293b" className="opacity-70" />
            <MiniMap
              nodeColor={(node) => (node.data.variant === "item" ? "#8b5cf6" : "#0ea5e9")}
              nodeStrokeColor={() => "#94a3b8"}
              maskColor="rgba(15, 23, 42, 0.85)"
            />
            <Controls position="bottom-right" />
          </ReactFlow>
        </div>
      </div>

      <div className="col-span-5 xl:col-span-1">
        <EditorPanel title="Item flow insights">
          <div className="space-y-4">
            <div className="space-y-2">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-300">Dataset overview</h3>
              <ul className="space-y-2 text-xs leading-relaxed text-slate-300">
              <li className="flex items-center justify-between gap-3">
                <span>Total items analysed</span>
                <span className="font-semibold text-slate-100">{totalItems}</span>
              </li>
              <li className="flex items-center justify-between gap-3">
                <span>Items without sources</span>
                <span className="font-semibold text-rose-200">{flaggedCounts.missingSources}</span>
              </li>
              <li className="flex items-center justify-between gap-3">
                <span>Orphaned items</span>
                <span className="font-semibold text-amber-200">{flaggedCounts.orphaned}</span>
              </li>
              <li className="flex items-center justify-between gap-3">
                <span>Surplus awards detected</span>
                <span className="font-semibold text-sky-200">{flaggedCounts.surplusAwards}</span>
              </li>
              <li className="flex items-center justify-between gap-3">
                <span>Consumption deficits</span>
                <span className="font-semibold text-sky-200">{flaggedCounts.consumptionDeficit}</span>
              </li>
              <li className="flex items-center justify-between gap-3">
                <span>Unreachable item sources</span>
                <span className="font-semibold text-rose-200">{flaggedCounts.unreachableSources}</span>
              </li>
            </ul>
            </div>

            <div className="space-y-2">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-300">Scene source tracking</h3>
              {sourceSummaries.length > 0 ? (
                <ul className="space-y-2 text-xs leading-relaxed text-slate-300">
                  {sourceSummaries.slice(0, SOURCE_SUMMARY_LIMIT).map((summary) => (
                    <li
                      key={`source-summary-${summary.sceneId}`}
                      className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3"
                    >
                      <div className="flex flex-wrap items-baseline justify-between gap-3">
                        <button
                          type="button"
                          onClick={() => handleOpenScene(summary.sceneId)}
                          className="text-sm font-semibold text-emerald-200 transition hover:text-emerald-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-300"
                        >
                          {summary.sceneId}
                        </button>
                        <span className="text-[11px] uppercase tracking-wide text-emerald-300/80">
                          {formatCountLabel(summary.itemCount, "item", "items")} · {formatCountLabel(summary.commandCount, "command", "commands")}
                        </span>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-1 text-[11px] text-emerald-100">
                        {summary.itemIds.map((itemId) => (
                          <span
                            key={`source-summary-${summary.sceneId}-${itemId}`}
                            className="rounded-md bg-emerald-500/10 px-2 py-1 text-emerald-100/90"
                          >
                            {itemId}
                          </span>
                        ))}
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs leading-relaxed text-slate-400">
                  No scenes currently award items in this dataset. Once scenes include item rewards they will appear here.
                </p>
              )}
              {sourceSummaries.length > SOURCE_SUMMARY_LIMIT ? (
                <p className="text-[11px] text-slate-500">
                  Showing top {SOURCE_SUMMARY_LIMIT} of {sourceSummaries.length} scenes that award items.
                </p>
              ) : null}
            </div>

            <div className="space-y-2">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-300">Scene usage tracking</h3>
              {requirementSummaries.length > 0 ? (
                <ul className="space-y-2 text-xs leading-relaxed text-slate-300">
                  {requirementSummaries.slice(0, REQUIREMENT_SUMMARY_LIMIT).map((summary) => (
                    <li
                      key={`usage-summary-${summary.sceneId}`}
                      className="rounded-lg border border-sky-500/20 bg-sky-500/5 p-3"
                    >
                      <div className="flex flex-wrap items-baseline justify-between gap-3">
                        <button
                          type="button"
                          onClick={() => handleOpenScene(summary.sceneId)}
                          className="text-sm font-semibold text-sky-200 transition hover:text-sky-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-300"
                        >
                          {summary.sceneId}
                        </button>
                        <span className="text-[11px] uppercase tracking-wide text-sky-200/80">
                          {formatCountLabel(summary.itemCount, "item", "items")} · {formatCountLabel(summary.commandCount, "command", "commands")}
                        </span>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-1 text-[11px] text-sky-100">
                        {summary.itemIds.map((itemId) => (
                          <span
                            key={`usage-summary-${summary.sceneId}-${itemId}`}
                            className="rounded-md bg-sky-500/10 px-2 py-1 text-sky-100/90"
                          >
                            {itemId}
                          </span>
                        ))}
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs leading-relaxed text-slate-400">
                  No scenes currently require items. Requirements will appear once transitions demand inventory items.
                </p>
              )}
              {requirementSummaries.length > REQUIREMENT_SUMMARY_LIMIT ? (
                <p className="text-[11px] text-slate-500">
                  Showing top {REQUIREMENT_SUMMARY_LIMIT} of {requirementSummaries.length} scenes that require items.
                </p>
              ) : null}
            </div>

            <div className="space-y-2">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-300">Legend</h3>
              <ul className="space-y-2 text-xs text-slate-300">
                <li className="flex items-center gap-2">
                <span className="inline-flex h-3 w-3 rounded-full bg-emerald-400" aria-hidden />
                Scene awards the item
              </li>
              <li className="flex items-center gap-2">
                <span className="inline-flex h-3 w-3 rounded-full bg-sky-400" aria-hidden />
                Scene requires the item
              </li>
              <li className="flex items-center gap-2">
                <span className="inline-flex h-3 w-3 rounded-full bg-rose-400" aria-hidden />
                Scene consumes the item
              </li>
            </ul>
            <p className="text-[11px] leading-relaxed text-slate-400">
              Arrow direction mirrors item flow: green edges move from scenes to the items they award, while blue and rose edges
              flow from items to the scenes that require or consume them.
            </p>
          </div>

          <div className="space-y-2">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-300">Focused item details</h3>
            {selectedItemDetail ? (
              <div className="space-y-3 text-xs leading-relaxed text-slate-300">
                <div className="flex items-center gap-2 text-sm font-semibold text-slate-100">
                  <span className="inline-flex h-2 w-2 rounded-full bg-violet-400" aria-hidden />
                  {selectedItemDetail.item}
                </div>
                <div className="grid gap-3">
                  <div>
                    <h4 className="text-[11px] uppercase tracking-wide text-slate-400">Awarded by</h4>
                    {selectedItemDetail.sources.length > 0 ? (
                      <ul className="mt-1 space-y-1">
                        {selectedItemDetail.sources.map((reference) => (
                          <li key={`source-${reference.scene_id}-${reference.command}`} className="flex items-center justify-between gap-3">
                            <span>{reference.scene_id}</span>
                            <span className="font-mono text-[11px] text-emerald-200">{reference.command}</span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-1 text-slate-500">No scenes currently award this item.</p>
                    )}
                  </div>
                  <div>
                    <h4 className="text-[11px] uppercase tracking-wide text-slate-400">Required by</h4>
                    {selectedItemDetail.requirements.length > 0 ? (
                      <ul className="mt-1 space-y-1">
                        {selectedItemDetail.requirements.map((reference) => (
                          <li key={`requirement-${reference.scene_id}-${reference.command}`} className="flex items-center justify-between gap-3">
                            <span>{reference.scene_id}</span>
                            <span className="font-mono text-[11px] text-sky-200">{reference.command}</span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-1 text-slate-500">No transitions currently require this item.</p>
                    )}
                  </div>
                  <div>
                    <h4 className="text-[11px] uppercase tracking-wide text-slate-400">Consumed by</h4>
                    {selectedItemDetail.consumptions.length > 0 ? (
                      <ul className="mt-1 space-y-1">
                        {selectedItemDetail.consumptions.map((reference) => (
                          <li key={`consumption-${reference.scene_id}-${reference.command}`} className="flex items-center justify-between gap-3">
                            <span>{reference.scene_id}</span>
                            <span className="font-mono text-[11px] text-rose-200">{reference.command}</span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-1 text-slate-500">No transitions consume this item.</p>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-xs leading-relaxed text-slate-400">
                Select an item to see which scenes award, require, and consume it. The graph focuses on the connected scenes so
                you can trace how the item moves through the adventure.
              </p>
            )}
          </div>
          </div>
        </EditorPanel>
      </div>
    </div>
  );
};

export default ItemFlowPage;
