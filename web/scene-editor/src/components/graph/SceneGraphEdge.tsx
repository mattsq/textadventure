import React from "react";
import {
  BaseEdge,
  EdgeLabelRenderer,
  getSmoothStepPath,
  type EdgeProps,
} from "reactflow";

const classNames = (
  ...values: Array<string | false | null | undefined>
): string => values.filter(Boolean).join(" ");

export type SceneGraphEdgeVariant = "default" | "conditional" | "terminal";

export interface SceneGraphEdgeActivateContext {
  readonly edgeId: string;
  readonly sceneId: string;
  readonly command: string;
}

export interface SceneGraphEdgeData {
  readonly command: string;
  readonly narration: string;
  readonly isTerminal: boolean;
  readonly item?: string | null;
  readonly requires: readonly string[];
  readonly consumes: readonly string[];
  readonly records: readonly string[];
  readonly failureNarration?: string | null;
  readonly overrideCount: number;
  readonly variant: SceneGraphEdgeVariant;
  readonly hasRequirements: boolean;
  readonly labelBackground: string;
  readonly labelBorder: string;
  readonly labelTextColor: string;
  readonly sourceSceneId: string;
  readonly onOpen?: (context: SceneGraphEdgeActivateContext) => void;
}

const variantAccentClasses: Record<SceneGraphEdgeVariant, string> = {
  default: "bg-slate-300/90",
  conditional: "bg-sky-400/90",
  terminal: "bg-rose-400/90",
};

const variantDescriptor: Record<SceneGraphEdgeVariant, string> = {
  default: "Transition",
  conditional: "Requires", // indicates requirement presence when paired with command label
  terminal: "Ending",
};

export const SceneGraphEdge: React.FC<EdgeProps<SceneGraphEdgeData>> = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  markerEnd,
  style,
  data,
  selected,
}) => {
  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
  });

  const isInteractive = typeof data?.onOpen === "function";

  const handleActivate = (
    event: React.MouseEvent<HTMLDivElement> | React.KeyboardEvent<HTMLDivElement>,
  ) => {
    event.stopPropagation();
    if (!data?.onOpen || !data.sourceSceneId) {
      return;
    }
    data.onOpen({ edgeId: id, sceneId: data.sourceSceneId, command: data.command });
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      handleActivate(event);
    }
  };

  return (
    <>
      <BaseEdge id={id} path={edgePath} markerEnd={markerEnd} style={style} />
      <EdgeLabelRenderer>
        <div
          className="pointer-events-none absolute"
          style={{
            transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
          }}
        >
          <div
            className={classNames(
              "pointer-events-auto inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide shadow-lg shadow-slate-900/60 backdrop-blur",
              isInteractive
                ? "cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-300"
                : undefined,
              selected ? "ring-2 ring-sky-400/70" : "ring-1 ring-slate-900/70",
            )}
            style={{
              backgroundColor: data?.labelBackground,
              borderColor: data?.labelBorder,
              color: data?.labelTextColor,
            }}
            title={
              data
                ? `${data.command}\n${data.narration || ""}`.trim()
                : undefined
            }
            role={isInteractive ? "button" : undefined}
            tabIndex={isInteractive ? 0 : undefined}
            aria-label={
              isInteractive
                ? `Edit transition ${data?.command ?? ""}`.trim()
                : undefined
            }
            onClick={isInteractive ? handleActivate : undefined}
            onKeyDown={isInteractive ? handleKeyDown : undefined}
          >
            <span
              className={classNames(
                "h-2 w-2 shrink-0 rounded-full shadow", // accent dot
                data ? variantAccentClasses[data.variant] : undefined,
              )}
              aria-hidden
            />
            <span className="max-w-[180px] truncate">{data?.command ?? ""}</span>
            {data?.variant === "conditional" ? (
              <span className="text-[10px] font-semibold uppercase tracking-widest text-sky-100/90">
                {variantDescriptor.conditional}
              </span>
            ) : null}
            {data?.variant === "terminal" ? (
              <span className="text-[10px] font-semibold uppercase tracking-widest text-rose-100/90">
                {variantDescriptor.terminal}
              </span>
            ) : null}
          </div>
        </div>
      </EdgeLabelRenderer>
    </>
  );
};

export default SceneGraphEdge;
