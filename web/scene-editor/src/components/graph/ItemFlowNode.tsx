import React from "react";
import { Handle, Position, type NodeProps } from "reactflow";

import { Badge } from "../display";

const classNames = (...values: Array<string | false | null | undefined>): string =>
  values.filter(Boolean).join(" ");

export type ItemFlowSceneRelation = "source" | "requirement" | "consumption";

export interface ItemFlowItemNodeData {
  readonly variant: "item";
  readonly itemId: string;
  readonly sourceCount: number;
  readonly requirementCount: number;
  readonly consumptionCount: number;
  readonly isOrphaned: boolean;
  readonly isMissingSource: boolean;
  readonly hasSurplusAwards: boolean;
  readonly hasConsumptionDeficit: boolean;
}

export interface ItemFlowSceneNodeData {
  readonly variant: "scene";
  readonly sceneId: string;
  readonly relationTypes: readonly ItemFlowSceneRelation[];
  readonly referenceCount: number;
  readonly onOpenScene?: (sceneId: string) => void;
}

export type ItemFlowNodeData = ItemFlowItemNodeData | ItemFlowSceneNodeData;

const relationVariantClasses: Record<ItemFlowSceneRelation, string> = {
  source: "bg-emerald-500/15 text-emerald-200 border border-emerald-500/40",
  requirement: "bg-sky-500/15 text-sky-200 border border-sky-500/40",
  consumption: "bg-rose-500/15 text-rose-200 border border-rose-500/40",
};

const relationLabels: Record<ItemFlowSceneRelation, string> = {
  source: "Awards item",
  requirement: "Requires item",
  consumption: "Consumes item",
};

const nodeContainerBase =
  "relative w-[260px] rounded-xl border border-slate-600/60 bg-slate-950/70 p-4 shadow-xl shadow-slate-950/40";

export const ItemFlowNode: React.FC<NodeProps<ItemFlowNodeData>> = ({ data }) => {
  const isItemNode = data.variant === "item";
  const containerClassName = classNames(
    nodeContainerBase,
    isItemNode ? "ring-2 ring-violet-400/60" : "ring-1 ring-slate-500/40",
  );

  const content = isItemNode ? (
    <div className="space-y-3">
      <div className="space-y-1">
        <p className="text-[11px] uppercase tracking-wide text-slate-500">Item</p>
        <p className="text-lg font-semibold text-slate-100" aria-label={`Item ${data.itemId}`}>
          {data.itemId}
        </p>
      </div>
      <dl className="grid grid-cols-2 gap-2 text-xs text-slate-200">
        <div className="space-y-1 rounded-md bg-slate-800/60 p-2">
          <dt className="text-[10px] uppercase tracking-wide text-slate-400">Sources</dt>
          <dd className="font-semibold text-emerald-200">{data.sourceCount}</dd>
        </div>
        <div className="space-y-1 rounded-md bg-slate-800/60 p-2">
          <dt className="text-[10px] uppercase tracking-wide text-slate-400">Requirements</dt>
          <dd className="font-semibold text-sky-200">{data.requirementCount}</dd>
        </div>
        <div className="space-y-1 rounded-md bg-slate-800/60 p-2">
          <dt className="text-[10px] uppercase tracking-wide text-slate-400">Consumptions</dt>
          <dd className="font-semibold text-rose-200">{data.consumptionCount}</dd>
        </div>
      </dl>
      <div className="flex flex-wrap gap-2">
        {data.isOrphaned ? (
          <Badge variant="warning" size="sm">
            Orphaned
          </Badge>
        ) : null}
        {data.isMissingSource ? (
          <Badge variant="danger" size="sm">
            Missing source
          </Badge>
        ) : null}
        {data.hasSurplusAwards ? (
          <Badge variant="info" size="sm">
            Surplus awards
          </Badge>
        ) : null}
        {data.hasConsumptionDeficit ? (
          <Badge variant="info" size="sm">
            Consumption deficit
          </Badge>
        ) : null}
      </div>
    </div>
  ) : (
    <div className="space-y-3">
      <div className="space-y-1">
        <p className="text-[11px] uppercase tracking-wide text-slate-500">Scene</p>
        <p className="text-lg font-semibold text-slate-100">{data.sceneId}</p>
      </div>
      <p className="text-xs leading-relaxed text-slate-300">
        Referenced in {data.referenceCount} {data.referenceCount === 1 ? "transition" : "transitions"} for this
        view.
      </p>
      <div className="flex flex-wrap gap-2">
        {data.relationTypes.map((relation) => (
          <span
            key={relation}
            className={classNames(
              "rounded-full px-2 py-1 text-[11px] font-medium uppercase tracking-wide",
              relationVariantClasses[relation],
            )}
          >
            {relationLabels[relation]}
          </span>
        ))}
      </div>
      {data.onOpenScene ? (
        <button
          type="button"
          onClick={() => data.onOpenScene?.(data.sceneId)}
          className="inline-flex items-center justify-center rounded-md bg-violet-500/90 px-3 py-1.5 text-xs font-semibold text-white shadow-sm shadow-violet-500/40 transition hover:bg-violet-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-300"
        >
          Open scene details
        </button>
      ) : null}
    </div>
  );

  return (
    <div className={containerClassName} role="group" aria-label={isItemNode ? `Item ${data.itemId}` : `Scene ${data.sceneId}`}>
      <Handle type="target" position={Position.Left} className="h-3 w-3 rounded-full border-2 border-slate-950 bg-slate-100" />
      <Handle type="source" position={Position.Right} className="h-3 w-3 rounded-full border-2 border-slate-950 bg-slate-100" />
      {content}
    </div>
  );
};

ItemFlowNode.displayName = "ItemFlowNode";

export default ItemFlowNode;
