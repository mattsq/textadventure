import React from "react";
import {
  Handle,
  Position,
  type NodeProps,
} from "reactflow";

import {
  Badge,
  ValidationStatusIndicator,
  VALIDATION_STATUS_DESCRIPTORS,
} from "../display";
import type { ValidationState } from "../../state";

const classNames = (...values: Array<string | false | null | undefined>): string =>
  values.filter(Boolean).join(" ");

export type SceneGraphNodeVariant = "scene" | "terminal";

export type SceneGraphSceneType = "start" | "end" | "branch" | "linear";

export interface SceneGraphSceneNodeData {
  readonly variant: "scene";
  readonly id: string;
  readonly label: string;
  readonly description: string;
  readonly sceneType: SceneGraphSceneType;
  readonly validationStatus: ValidationState;
  readonly choiceCount: number;
  readonly transitionCount: number;
  readonly hasTerminalTransition: boolean;
  readonly isReachable: boolean;
  readonly isHighlighted?: boolean;
  readonly isDimmed?: boolean;
  readonly onOpen?: (sceneId: string) => void;
  readonly pathHighlightRole?: "start" | "end" | "intermediate";
  readonly criticalPathRole?: "start" | "end" | "intermediate";
}

export interface SceneGraphTerminalNodeData {
  readonly variant: "terminal";
  readonly id: string;
  readonly label: string;
  readonly command: string;
  readonly narration: string;
  readonly sourceScene: string;
  readonly isHighlighted?: boolean;
  readonly isDimmed?: boolean;
}

export type SceneGraphNodeData =
  | SceneGraphSceneNodeData
  | SceneGraphTerminalNodeData;

const sceneValidationClasses: Record<ValidationState, string> = {
  valid:
    "border-emerald-500/60 bg-slate-950/50 shadow-lg shadow-emerald-500/20",
  warnings:
    "border-amber-400/60 bg-slate-950/50 shadow-lg shadow-amber-500/20",
  errors:
    "border-rose-500/60 bg-slate-950/50 shadow-lg shadow-rose-500/20",
};

const unreachableSceneClasses =
  "border-rose-500/70 bg-rose-500/10 shadow-lg shadow-rose-500/30";

const terminalClasses =
  "border-rose-500/70 bg-rose-500/10 shadow-lg shadow-rose-500/20";

const handleClassName =
  "h-3 w-3 rounded-full border-2 border-slate-950 bg-slate-100";

const sceneTypeAccentBase =
  "before:absolute before:left-0 before:top-0 before:h-1 before:w-full before:content-['']";

const sceneTypeAccentClasses: Record<SceneGraphSceneType, string> = {
  start: "ring-2 ring-sky-400/60 before:bg-sky-400/80",
  end: "ring-2 ring-rose-400/60 before:bg-rose-400/80",
  branch: "ring-2 ring-violet-400/60 before:bg-violet-400/80",
  linear: "ring-2 ring-slate-300/50 before:bg-slate-300/80",
};

const validationStatusAccentBase =
  "after:pointer-events-none after:absolute after:-left-1.5 after:top-3 after:bottom-3 after:w-1 after:rounded-full after:opacity-90 after:content-['']";

const validationStatusAccentClasses: Record<ValidationState, string> = {
  valid: "after:bg-emerald-400/90 after:shadow after:shadow-emerald-400/40",
  warnings: "after:bg-amber-400/90 after:shadow after:shadow-amber-400/40",
  errors: "after:bg-rose-400/90 after:shadow after:shadow-rose-400/40",
};

const sceneTypeLabels: Record<SceneGraphSceneType, string> = {
  start: "Start scene",
  end: "Ending scene",
  branch: "Branching scene",
  linear: "Linear scene",
};

export const SceneGraphNode: React.FC<NodeProps<SceneGraphNodeData>> = ({
  data,
}) => {
  const tooltipId = React.useId();

  const isSceneNode = data.variant === "scene";

  const handleActivate = React.useCallback(() => {
    if (!isSceneNode || !data.onOpen) {
      return;
    }
    data.onOpen(data.id);
  }, [data, isSceneNode]);

  const handleKeyDown = React.useCallback(
    (event: React.KeyboardEvent<HTMLDivElement>) => {
      if (!isSceneNode || !data.onOpen) {
        return;
      }

      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        data.onOpen(data.id);
      }
    },
    [data, isSceneNode],
  );

  const tooltipContent = React.useMemo(() => {
    if (data.variant === "scene") {
      const descriptor = VALIDATION_STATUS_DESCRIPTORS[data.validationStatus];
      return (
        <div className="space-y-2">
          <div className="space-y-1">
            <p className="text-[11px] uppercase tracking-wide text-slate-500">
              Scene overview
            </p>
            <p className="text-sm font-semibold text-slate-100">
              {data.label}
            </p>
            <p className="text-xs leading-relaxed text-slate-300">
              {data.description}
            </p>
          </div>
          <dl className="space-y-1 text-xs text-slate-200">
            <div className="flex items-center justify-between gap-3">
              <dt className="text-[10px] uppercase tracking-wide text-slate-500">
                Validation
              </dt>
              <dd className="font-medium text-slate-100">
                {descriptor.label}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="text-[10px] uppercase tracking-wide text-slate-500">
                Scene type
              </dt>
              <dd className="font-medium text-slate-100">
                {sceneTypeLabels[data.sceneType]}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="text-[10px] uppercase tracking-wide text-slate-500">
                Choices
              </dt>
              <dd className="font-medium text-slate-100">
                {data.choiceCount}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="text-[10px] uppercase tracking-wide text-slate-500">
                Transitions
              </dt>
              <dd className="font-medium text-slate-100">
                {data.transitionCount}
              </dd>
            </div>
            {data.hasTerminalTransition ? (
              <div className="flex items-center justify-between gap-3">
                <dt className="text-[10px] uppercase tracking-wide text-slate-500">
                  Has ending branch
                </dt>
                <dd className="font-medium text-slate-100">Yes</dd>
              </div>
            ) : null}
          </dl>
          {!data.isReachable ? (
            <p className="rounded-md border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-[11px] font-medium text-rose-200">
              This scene is currently unreachable from the configured start scene.
            </p>
          ) : null}
        </div>
      );
    }

    return (
      <div className="space-y-2">
        <div className="space-y-1">
          <p className="text-[11px] uppercase tracking-wide text-slate-500">
            Terminal branch
          </p>
          <p className="text-sm font-semibold text-slate-100">
            {data.command}
          </p>
        </div>
        <p className="text-xs leading-relaxed text-slate-300">{data.narration}</p>
        <p className="text-[10px] uppercase tracking-wide text-slate-500">
          Origin scene: <span className="text-slate-100">{data.sourceScene}</span>
        </p>
      </div>
    );
  }, [data]);

  return (
    <div
      className={classNames(
        "group relative w-64 rounded-xl border px-4 py-3 text-left focus:outline-none focus:ring-2 focus:ring-slate-200/60", // base
        isSceneNode
          ? sceneValidationClasses[data.validationStatus]
          : terminalClasses,
        isSceneNode && sceneTypeAccentBase,
        isSceneNode && sceneTypeAccentClasses[data.sceneType],
        isSceneNode && validationStatusAccentBase,
        isSceneNode && validationStatusAccentClasses[data.validationStatus],
        isSceneNode && !data.isReachable && unreachableSceneClasses,
        isSceneNode && data.onOpen ? "cursor-pointer" : undefined,
        data.isHighlighted
          ? "outline outline-2 outline-offset-4 outline-indigo-400"
          : undefined,
        data.isDimmed ? "opacity-40 saturate-75" : undefined,
      )}
      tabIndex={0}
      aria-describedby={tooltipId}
      role={isSceneNode && data.onOpen ? "button" : undefined}
      onClick={isSceneNode ? handleActivate : undefined}
      onKeyDown={isSceneNode ? handleKeyDown : undefined}
    >
      <Handle
        type="target"
        position={Position.Left}
        isConnectable={false}
        className={handleClassName}
      />
      {isSceneNode ? (
        <Handle
          type="source"
          position={Position.Right}
          isConnectable={false}
          className={handleClassName}
        />
      ) : null}
      <div className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1">
            <p className="text-[11px] uppercase tracking-wide text-slate-300/80">
              {isSceneNode
                ? sceneTypeLabels[data.sceneType]
                : `Ending from ${data.sourceScene}`}
            </p>
            <h3 className="text-base font-semibold text-slate-50">
              {data.label}
            </h3>
          </div>
          {isSceneNode ? (
            <ValidationStatusIndicator
              status={data.validationStatus}
              hideLabel
              size="sm"
              className="shadow"
            />
          ) : (
            <Badge variant="danger" size="sm">
              Terminal
            </Badge>
          )}
        </div>
        {isSceneNode ? (
          <>
            <p className="text-xs leading-relaxed text-slate-200">
              {data.description}
            </p>
            <div className="flex flex-wrap gap-2 text-[11px] uppercase tracking-wide text-slate-200">
              <Badge variant="info" size="sm">
                {data.choiceCount} choices
              </Badge>
              <Badge variant="neutral" size="sm">
                {data.transitionCount} transitions
              </Badge>
              {data.hasTerminalTransition ? (
                <Badge variant="warning" size="sm">
                  Has ending
                </Badge>
              ) : null}
              {!data.isReachable ? (
                <Badge variant="danger" size="sm">
                  Unreachable
                </Badge>
              ) : null}
              {data.pathHighlightRole === "start" ? (
                <Badge variant="info" size="sm">
                  Path start
                </Badge>
              ) : null}
              {data.pathHighlightRole === "end" ? (
                <Badge variant="danger" size="sm">
                  Path end
                </Badge>
              ) : null}
              {data.pathHighlightRole === "intermediate" ? (
                <Badge variant="neutral" size="sm">
                  On path
                </Badge>
              ) : null}
              {data.criticalPathRole === "start" ? (
                <Badge variant="success" size="sm">
                  Critical start
                </Badge>
              ) : null}
              {data.criticalPathRole === "end" ? (
                <Badge variant="danger" size="sm">
                  Critical end
                </Badge>
              ) : null}
              {data.criticalPathRole === "intermediate" ? (
                <Badge variant="info" size="sm">
                  Critical path
                </Badge>
              ) : null}
            </div>
          </>
        ) : (
          <>
            <p className="text-xs leading-relaxed text-slate-200">
              {data.narration}
            </p>
            <div className="flex flex-wrap gap-2 text-[11px] uppercase tracking-wide text-slate-200">
              <Badge variant="neutral" size="sm">
                {data.command}
              </Badge>
              <Badge variant="danger" size="sm">
                Ending
              </Badge>
            </div>
          </>
        )}
      </div>
      <div
        id={tooltipId}
        role="tooltip"
        className="pointer-events-none absolute left-1/2 top-full z-20 hidden w-72 -translate-x-1/2 translate-y-3 rounded-lg border border-slate-800/80 bg-slate-950/90 p-4 text-xs leading-relaxed text-slate-200 shadow-2xl shadow-slate-950/80 group-focus-visible:block group-hover:block"
      >
        {tooltipContent}
      </div>
    </div>
  );
};

export default SceneGraphNode;
