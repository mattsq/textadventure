import React from "react";
import { TextField } from "../forms";

type ClassValue = string | false | null | undefined;

const classNames = (...values: readonly ClassValue[]): string =>
  values.filter(Boolean).join(" ");

const HISTORY_GROUPS = [
  {
    id: "requiresAll" as const,
    label: "Must include every record",
    shortLabel: "All",
    description:
      "Players must have recorded every listed history entry for the condition to pass.",
    accentClassName:
      "border-emerald-500/60 bg-emerald-500/10 text-emerald-100",
  },
  {
    id: "requiresAny" as const,
    label: "Requires at least one record",
    shortLabel: "Any",
    description:
      "The override applies when players have recorded any of the listed history entries.",
    accentClassName: "border-sky-500/60 bg-sky-500/10 text-sky-100",
  },
  {
    id: "forbidsAny" as const,
    label: "Hidden when records are present",
    shortLabel: "Forbidden",
    description:
      "Players must not have recorded any of the listed history entries for the condition to pass.",
    accentClassName: "border-rose-500/60 bg-rose-500/10 text-rose-100",
  },
] satisfies readonly [
  {
    readonly id: "requiresAll";
    readonly label: string;
    readonly shortLabel: string;
    readonly description: string;
    readonly accentClassName: string;
  },
  {
    readonly id: "requiresAny";
    readonly label: string;
    readonly shortLabel: string;
    readonly description: string;
    readonly accentClassName: string;
  },
  {
    readonly id: "forbidsAny";
    readonly label: string;
    readonly shortLabel: string;
    readonly description: string;
    readonly accentClassName: string;
  },
];

type HistoryConditionGroupId = (typeof HISTORY_GROUPS)[number]["id"];

interface HistoryConditionBuilderValues {
  readonly requiresAll: readonly string[];
  readonly requiresAny: readonly string[];
  readonly forbidsAny: readonly string[];
}

export interface HistoryConditionBuilderProps {
  readonly className?: string;
  readonly disabled?: boolean;
  readonly values: HistoryConditionBuilderValues;
  readonly options: readonly string[];
  readonly onChange: (values: HistoryConditionBuilderValues) => void;
}

interface DragPayload {
  readonly groupId: HistoryConditionGroupId;
  readonly value: string;
}

type MutableHistoryConditionBuilderValues = {
  -readonly [Key in keyof HistoryConditionBuilderValues]: string[];
};

const DRAG_DATA_MIME = "application/x-scene-editor-history-condition";

const normaliseValue = (value: string): string => value.trim();

const dedupeList = (values: readonly string[]): string[] => {
  const seen = new Set<string>();
  const result: string[] = [];

  for (const value of values) {
    const trimmed = normaliseValue(value);
    if (!trimmed) {
      continue;
    }
    const key = trimmed.toLowerCase();
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    result.push(trimmed);
  }

  return result;
};

const removeValueFromGroup = (
  values: readonly string[],
  target: string,
): string[] => {
  const lowerTarget = target.toLowerCase();
  return values.filter((value) => value.toLowerCase() !== lowerTarget);
};

const moveConditionValue = (
  draft: MutableHistoryConditionBuilderValues,
  targetGroup: HistoryConditionGroupId,
  value: string,
  targetIndex: number | null,
): void => {
  const trimmed = normaliseValue(value);
  if (!trimmed) {
    return;
  }

  draft.requiresAll = removeValueFromGroup(draft.requiresAll, trimmed);
  draft.requiresAny = removeValueFromGroup(draft.requiresAny, trimmed);
  draft.forbidsAny = removeValueFromGroup(draft.forbidsAny, trimmed);

  const targetList = [...draft[targetGroup]];
  const insertionIndex = (() => {
    if (targetIndex === null || Number.isNaN(targetIndex)) {
      return targetList.length;
    }
    if (targetIndex < 0) {
      return 0;
    }
    if (targetIndex > targetList.length) {
      return targetList.length;
    }
    return targetIndex;
  })();

  targetList.splice(insertionIndex, 0, trimmed);
  draft[targetGroup] = targetList;
};

export const HistoryConditionBuilder: React.FC<
  HistoryConditionBuilderProps
> = ({ className, disabled = false, values, options, onChange }) => {
  const [activeAddGroup, setActiveAddGroup] = React.useState<HistoryConditionGroupId>(
    "requiresAll",
  );
  const [pendingValue, setPendingValue] = React.useState("");
  const [activeDropGroup, setActiveDropGroup] =
    React.useState<HistoryConditionGroupId | null>(null);
  const datalistId = React.useId();

  const updateValues = React.useCallback(
    (updater: (draft: MutableHistoryConditionBuilderValues) => void) => {
      const draft: MutableHistoryConditionBuilderValues = {
        requiresAll: [...values.requiresAll],
        requiresAny: [...values.requiresAny],
        forbidsAny: [...values.forbidsAny],
      };
      updater(draft);
      onChange({
        requiresAll: dedupeList(draft.requiresAll),
        requiresAny: dedupeList(draft.requiresAny),
        forbidsAny: dedupeList(draft.forbidsAny),
      });
    },
    [onChange, values.forbidsAny, values.requiresAll, values.requiresAny],
  );

  const handleRemoveValue = React.useCallback(
    (groupId: HistoryConditionGroupId, value: string) => {
      updateValues((draft) => {
        draft[groupId] = removeValueFromGroup(draft[groupId], value);
      });
    },
    [updateValues],
  );

  const handleDragStart = React.useCallback(
    (
      event: React.DragEvent<HTMLDivElement>,
      groupId: HistoryConditionGroupId,
      value: string,
    ) => {
      if (disabled) {
        event.preventDefault();
        return;
      }

      const payload: DragPayload = { groupId, value };
      event.dataTransfer.setData(DRAG_DATA_MIME, JSON.stringify(payload));
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setDragImage(event.currentTarget, 12, 12);
      setActiveDropGroup(groupId);
    },
    [disabled],
  );

  const clearDragState = React.useCallback(() => {
    setActiveDropGroup(null);
  }, []);

  const handleDragEnd = React.useCallback(() => {
    clearDragState();
  }, [clearDragState]);

  const handleGroupDragOver = React.useCallback(
    (event: React.DragEvent<HTMLUListElement>, groupId: HistoryConditionGroupId) => {
      if (disabled) {
        return;
      }
      if (!event.dataTransfer.types.includes(DRAG_DATA_MIME)) {
        return;
      }
      event.preventDefault();
      event.dataTransfer.dropEffect = "move";
      if (activeDropGroup !== groupId) {
        setActiveDropGroup(groupId);
      }
    },
    [activeDropGroup, disabled],
  );

  const handleGroupDrop = React.useCallback(
    (event: React.DragEvent<HTMLUListElement>, groupId: HistoryConditionGroupId) => {
      if (disabled) {
        return;
      }
      if (!event.dataTransfer.types.includes(DRAG_DATA_MIME)) {
        return;
      }
      event.preventDefault();
      const rawPayload = event.dataTransfer.getData(DRAG_DATA_MIME);
      if (!rawPayload) {
        clearDragState();
        return;
      }
      try {
        const payload = JSON.parse(rawPayload) as DragPayload;
        updateValues((draft) => {
          moveConditionValue(draft, groupId, payload.value, null);
        });
      } catch (error) {
        console.error("Failed to parse drag payload", error);
      }
      clearDragState();
    },
    [clearDragState, disabled, updateValues],
  );

  const handleGroupDragLeave = React.useCallback(
    (event: React.DragEvent<HTMLUListElement>, groupId: HistoryConditionGroupId) => {
      if (disabled) {
        return;
      }
      const nextTarget = event.relatedTarget as Node | null;
      if (!nextTarget || !event.currentTarget.contains(nextTarget)) {
        setActiveDropGroup((previous) =>
          previous === groupId ? null : previous,
        );
      }
    },
    [disabled],
  );

  const handleItemDrop = React.useCallback(
    (
      event: React.DragEvent<HTMLLIElement>,
      groupId: HistoryConditionGroupId,
      index: number,
    ) => {
      if (disabled) {
        return;
      }
      if (!event.dataTransfer.types.includes(DRAG_DATA_MIME)) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      const rawPayload = event.dataTransfer.getData(DRAG_DATA_MIME);
      if (!rawPayload) {
        clearDragState();
        return;
      }
      try {
        const payload = JSON.parse(rawPayload) as DragPayload;
        updateValues((draft) => {
          moveConditionValue(draft, groupId, payload.value, index);
        });
      } catch (error) {
        console.error("Failed to parse drag payload", error);
      }
      clearDragState();
    },
    [clearDragState, disabled, updateValues],
  );

  const handleAddCondition = React.useCallback(
    (event?: React.FormEvent<HTMLFormElement>) => {
      event?.preventDefault();
      if (disabled) {
        return;
      }
      const trimmed = normaliseValue(pendingValue);
      if (!trimmed) {
        setPendingValue("");
        return;
      }
      updateValues((draft) => {
        draft.requiresAll = removeValueFromGroup(draft.requiresAll, trimmed);
        draft.requiresAny = removeValueFromGroup(draft.requiresAny, trimmed);
        draft.forbidsAny = removeValueFromGroup(draft.forbidsAny, trimmed);
        const targetList = [...draft[activeAddGroup]];
        targetList.push(trimmed);
        draft[activeAddGroup] = targetList;
      });
      setPendingValue("");
    },
    [activeAddGroup, disabled, pendingValue, updateValues],
  );

  const groupedValues = React.useMemo(
    () => ({
      requiresAll: values.requiresAll,
      requiresAny: values.requiresAny,
      forbidsAny: values.forbidsAny,
    }),
    [values.forbidsAny, values.requiresAll, values.requiresAny],
  );

  return (
    <div
      className={classNames(
        "rounded-xl border border-slate-800/70 bg-slate-950/40 p-4 shadow-inner shadow-slate-950/20",
        className,
      )}
    >
      <div className="flex flex-col gap-1">
        <h5 className="text-sm font-semibold text-slate-200">
          History conditions
        </h5>
        <p className="text-xs text-slate-400">
          Drag history entries between buckets to control when this override applies.
        </p>
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        {HISTORY_GROUPS.map((group) => {
          const valuesForGroup = groupedValues[group.id];
          const isDropTarget = activeDropGroup === group.id;

          return (
            <section
              key={group.id}
              aria-label={group.label}
              className="flex flex-col gap-2"
            >
              <div
                className={classNames(
                  "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-wide",
                  group.accentClassName,
                )}
              >
                {group.shortLabel}
              </div>
              <p className="text-xs text-slate-400">{group.description}</p>
              <ul
                className={classNames(
                  "min-h-[5rem] rounded-lg border border-dashed border-slate-800/60 bg-slate-900/30 p-3 text-sm transition",
                  isDropTarget
                    ? "border-indigo-400/70 bg-indigo-500/10"
                    : "hover:border-slate-700/80",
                  disabled ? "opacity-60" : undefined,
                )}
                onDragOver={(event) => handleGroupDragOver(event, group.id)}
                onDrop={(event) => handleGroupDrop(event, group.id)}
                onDragLeave={(event) => handleGroupDragLeave(event, group.id)}
              >
                {valuesForGroup.length === 0 ? (
                  <li className="text-xs text-slate-500">Drop history entries here</li>
                ) : (
                  valuesForGroup.map((value, index) => (
                    <li
                      key={`${group.id}-${value}`}
                      onDrop={(event) => handleItemDrop(event, group.id, index)}
                      className="mb-2 last:mb-0"
                    >
                      <div
                        draggable={!disabled}
                        onDragStart={(event) =>
                          handleDragStart(event, group.id, value)
                        }
                        onDragEnd={handleDragEnd}
                        className="group flex items-center justify-between gap-3 rounded-md border border-slate-700/70 bg-slate-900/70 px-2 py-1 text-xs text-slate-200 shadow-sm transition hover:border-indigo-400/70 hover:text-indigo-100"
                      >
                        <span className="truncate" title={value}>
                          {value}
                        </span>
                        <button
                          type="button"
                          onClick={() => handleRemoveValue(group.id, value)}
                          disabled={disabled}
                          className={classNames(
                            "rounded px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide transition",
                            disabled
                              ? "cursor-not-allowed text-slate-600"
                              : "text-slate-400 hover:bg-red-500/20 hover:text-red-200",
                          )}
                        >
                          Remove
                        </button>
                      </div>
                    </li>
                  ))
                )}
              </ul>
            </section>
          );
        })}
      </div>
      <form
        className="mt-4 flex flex-col gap-3 lg:flex-row lg:items-end"
        onSubmit={(event) => {
          handleAddCondition(event);
        }}
      >
        <div className="flex-1">
          <TextField
            label="History entry"
            description="Type a history record and assign it to a bucket, then press Add."
            value={pendingValue}
            onChange={(event) => setPendingValue(event.target.value)}
            disabled={disabled}
            list={datalistId}
            placeholder="e.g. research_completed"
          />
          <datalist id={datalistId}>
            {options.map((option) => (
              <option key={option} value={option} />
            ))}
          </datalist>
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Assign to
          </span>
          <div className="flex gap-2">
            {HISTORY_GROUPS.map((group) => {
              const isSelected = activeAddGroup === group.id;
              return (
                <button
                  key={group.id}
                  type="button"
                  onClick={() => setActiveAddGroup(group.id)}
                  disabled={disabled}
                  className={classNames(
                    "rounded-md border px-3 py-1 text-xs font-semibold uppercase tracking-wide transition",
                    isSelected
                      ? "border-indigo-400/70 bg-indigo-500/20 text-indigo-100"
                      : "border-slate-700/70 text-slate-300 hover:border-indigo-400/70 hover:text-indigo-100",
                    disabled ? "cursor-not-allowed opacity-60" : undefined,
                  )}
                >
                  {group.shortLabel}
                </button>
              );
            })}
          </div>
        </div>
        <button
          type="submit"
          disabled={disabled}
          className={classNames(
            "inline-flex items-center justify-center rounded-md border border-indigo-400/70 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-indigo-100 transition",
            disabled
              ? "cursor-not-allowed border-slate-700/60 text-slate-500"
              : "hover:border-indigo-300 hover:bg-indigo-500/20",
          )}
        >
          Add condition
        </button>
      </form>
    </div>
  );
};

HistoryConditionBuilder.displayName = "HistoryConditionBuilder";

