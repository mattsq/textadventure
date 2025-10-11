import React from "react";
import { DataTable, type DataTableColumn } from "../display";
import type { SceneReferenceResource } from "../../api";
import type { SceneDeletionState } from "../../state";

export interface SceneDeletionDialogProps {
  readonly state: SceneDeletionState;
  readonly onCancel: () => void;
  readonly onConfirm: () => void;
}

const referenceColumns: readonly DataTableColumn<SceneReferenceResource>[] = [
  {
    id: "scene_id",
    header: "Referencing Scene",
    render: (reference) => (
      <span className="font-mono text-xs uppercase tracking-wide text-slate-200">
        {reference.scene_id}
      </span>
    ),
  },
  {
    id: "command",
    header: "Command",
    render: (reference) => (
      <span className="rounded-full bg-slate-900/80 px-2 py-1 font-mono text-[10px] uppercase tracking-wide text-slate-200">
        {reference.command}
      </span>
    ),
    className: "w-36",
  },
];

const spinner = (
  <span
    className="h-4 w-4 animate-spin rounded-full border-2 border-slate-500 border-t-transparent"
    aria-hidden
  />
);

export const SceneDeletionDialog: React.FC<SceneDeletionDialogProps> = ({
  state,
  onCancel,
  onConfirm,
}) => {
  const { status, scene, references, error } = state;
  const isOpen = status !== "idle" && scene !== null;

  if (!isOpen || !scene) {
    return null;
  }

  const totalReferences = references.length;
  const uniqueSceneCount = new Set(references.map((reference) => reference.scene_id)).size;
  const isBusy = status === "checking" || status === "deleting";
  const showReferenceTable = totalReferences > 0 && status !== "checking";
  const confirmDisabled = isBusy || (status !== "ready" && status !== "error");
  const cancelDisabled = status === "deleting";

  const confirmLabel =
    status === "error"
      ? "Retry deletion"
      : totalReferences > 0
        ? "Update references & delete"
        : "Delete scene";

  const impactSummary =
    totalReferences > 0
      ? [
          `Update ${totalReferences} transition${totalReferences === 1 ? "" : "s"} across ${uniqueSceneCount} scene${
            uniqueSceneCount === 1 ? "" : "s"
          } to remove links to "${scene.id}".`,
          "Each affected transition will become a terminal outcome until you retarget it.",
          "The scene definition will then be removed from the dataset.",
        ]
      : [
          "No other scenes reference this scene.",
          "The scene definition will be removed from the dataset.",
        ];

  let statusIndicator: React.ReactNode = null;
  if (status === "checking") {
    statusIndicator = (
      <div className="flex items-center gap-2 text-sm text-slate-300">
        {spinner}
        <span>Analysing dependencies…</span>
      </div>
    );
  } else if (status === "deleting") {
    statusIndicator = (
      <div className="flex items-center gap-2 text-sm text-slate-300">
        {spinner}
        <span>Updating references and deleting the scene…</span>
      </div>
    );
  } else if (status === "error" && error) {
    statusIndicator = (
      <div className="rounded-lg border border-rose-500/60 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
        {error}
      </div>
    );
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="scene-deletion-dialog-title"
    >
      <div className="mx-4 w-full max-w-3xl rounded-2xl border border-slate-800/70 bg-slate-900/95 shadow-2xl shadow-slate-950/50">
        <div className="flex items-start justify-between gap-4 border-b border-slate-800/70 px-6 py-4">
          <div>
            <h2
              id="scene-deletion-dialog-title"
              className="text-lg font-semibold text-rose-100"
            >
              Delete scene "{scene.id}"?
            </h2>
            <p className="mt-1 text-sm text-slate-300">
              Confirming this action will update dependent transitions and permanently remove the scene definition.
            </p>
          </div>
          <button
            type="button"
            onClick={onCancel}
            disabled={cancelDisabled}
            className="rounded-full border border-slate-700/70 bg-slate-900/70 p-2 text-slate-300 transition hover:text-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
            aria-label="Cancel deletion"
          >
            ×
          </button>
        </div>

        <div className="space-y-4 px-6 py-5">
          {statusIndicator}

          {(status === "ready" || status === "error") && (
            <ul className="list-disc space-y-1 pl-5 text-sm text-slate-300">
              {impactSummary.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          )}

          {showReferenceTable ? (
            <DataTable
              columns={referenceColumns}
              data={references}
              dense
              caption={`Transitions referencing "${scene.id}"`}
              emptyState="No referencing scenes detected."
              getRowKey={(reference, index) => `${reference.scene_id}:${reference.command}:${index}`}
            />
          ) : null}

          {status === "checking" && (
            <p className="text-sm text-slate-300">
              Gathering dependency information so the deletion can safely update affected scenes.
            </p>
          )}
        </div>

        <div className="flex flex-col gap-3 border-t border-slate-800/70 bg-slate-900/80 px-6 py-4 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onCancel}
            disabled={cancelDisabled}
            className="inline-flex items-center justify-center rounded-md border border-slate-700/70 px-4 py-2 text-sm font-medium text-slate-200 transition hover:bg-slate-800/80 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={confirmDisabled}
            className="inline-flex items-center justify-center rounded-md border border-rose-500/70 bg-rose-600/80 px-4 py-2 text-sm font-semibold text-rose-50 shadow-sm shadow-rose-900/40 transition hover:bg-rose-600 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
};

export default SceneDeletionDialog;
