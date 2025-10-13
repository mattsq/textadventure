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

export type SceneGraphEdgeVariant =
  | "default"
  | "conditional"
  | "consumable"
  | "reward"
  | "terminal";

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
  consumable: "bg-amber-400/90",
  reward: "bg-emerald-400/90",
  terminal: "bg-rose-400/90",
};

type SceneGraphEdgeBadgeTone =
  | "info"
  | "success"
  | "warning"
  | "danger"
  | "muted";

interface SceneGraphEdgeBadge {
  readonly id: string;
  readonly label: string;
  readonly tone: SceneGraphEdgeBadgeTone;
}

const badgeToneClasses: Record<SceneGraphEdgeBadgeTone, string> = {
  info: "border-sky-200/70 bg-sky-500/90 text-sky-50",
  success: "border-emerald-200/70 bg-emerald-500/90 text-emerald-50",
  warning: "border-amber-200/70 bg-amber-500/90 text-amber-50",
  danger: "border-rose-200/70 bg-rose-500/90 text-rose-50",
  muted: "border-slate-200/70 bg-slate-500/80 text-slate-50",
};

const variantBadges: Partial<Record<SceneGraphEdgeVariant, SceneGraphEdgeBadge>>
  = {
    conditional: {
      id: "variant-conditional",
      label: "Requires",
      tone: "info",
    },
    consumable: {
      id: "variant-consumable",
      label: "Consumes items",
      tone: "warning",
    },
    reward: {
      id: "variant-reward",
      label: "Rewards",
      tone: "success",
    },
    terminal: {
      id: "variant-terminal",
      label: "Ending",
      tone: "danger",
    },
  };

const buildBadges = (data: SceneGraphEdgeData | undefined): SceneGraphEdgeBadge[] => {
  if (!data) {
    return [];
  }

  const badges: SceneGraphEdgeBadge[] = [];
  const variantBadge = variantBadges[data.variant];
  if (variantBadge) {
    badges.push(variantBadge);
  }

  if (data.hasRequirements && data.variant !== "conditional") {
    badges.push({
      id: "requires",
      label: "Requires",
      tone: "info",
    });
  }

  if (data.consumes.length > 0 && data.variant !== "consumable") {
    badges.push({
      id: "consumes",
      label: "Consumes",
      tone: "warning",
    });
  }

  if (data.item) {
    badges.push({
      id: "rewards-item",
      label: "Grants item",
      tone: "success",
    });
  }

  if (data.records.length > 0) {
    badges.push({
      id: "records",
      label: "Records memory",
      tone: "muted",
    });
  }

  if (data.overrideCount > 0) {
    badges.push({
      id: "overrides",
      label: `Overrides (${data.overrideCount})`,
      tone: "muted",
    });
  }

  if ((data.failureNarration ?? "").trim() !== "") {
    badges.push({
      id: "failure",
      label: "Failure text",
      tone: "danger",
    });
  }

  return badges;
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
  const badges = React.useMemo(() => buildBadges(data), [data]);

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
            {badges.map((badge) => (
              <span
                key={badge.id}
                className={classNames(
                  "rounded-full border px-2 py-0.5 text-[9px] font-semibold uppercase tracking-widest",
                  badgeToneClasses[badge.tone],
                )}
              >
                {badge.label}
              </span>
            ))}
          </div>
        </div>
      </EdgeLabelRenderer>
    </>
  );
};

export default SceneGraphEdge;
