import React from "react";
import {
  Handle,
  Position,
  type NodeProps,
} from "reactflow";

import { Badge, ValidationStatusIndicator } from "../display";
import type { ValidationState } from "../../state";

const classNames = (...values: Array<string | false | null | undefined>): string =>
  values.filter(Boolean).join(" ");

export type SceneGraphNodeVariant = "scene" | "terminal";

export interface SceneGraphSceneNodeData {
  readonly variant: "scene";
  readonly id: string;
  readonly label: string;
  readonly description: string;
  readonly validationStatus: ValidationState;
  readonly choiceCount: number;
  readonly transitionCount: number;
  readonly hasTerminalTransition: boolean;
}

export interface SceneGraphTerminalNodeData {
  readonly variant: "terminal";
  readonly id: string;
  readonly label: string;
  readonly command: string;
  readonly narration: string;
  readonly sourceScene: string;
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

const terminalClasses =
  "border-rose-500/70 bg-rose-500/10 shadow-lg shadow-rose-500/20";

const handleClassName =
  "h-3 w-3 rounded-full border-2 border-slate-950 bg-slate-100";

export const SceneGraphNode: React.FC<NodeProps<SceneGraphNodeData>> = ({
  data,
}) => {
  return (
    <div
      className={classNames(
        "relative w-64 rounded-xl border px-4 py-3 text-left", // base
        data.variant === "scene"
          ? sceneValidationClasses[data.validationStatus]
          : terminalClasses,
      )}
    >
      <Handle
        type="target"
        position={Position.Left}
        isConnectable={false}
        className={handleClassName}
      />
      {data.variant === "scene" ? (
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
              {data.variant === "scene" ? "Scene" : `Ending from ${data.sourceScene}`}
            </p>
            <h3 className="text-base font-semibold text-slate-50">
              {data.label}
            </h3>
          </div>
          {data.variant === "scene" ? (
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
        {data.variant === "scene" ? (
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
    </div>
  );
};

export default SceneGraphNode;
