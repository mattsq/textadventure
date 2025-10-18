import React from "react";
import type { NarrationOverrideResource } from "../../api";
import { Card } from "../display";
import { MarkdownEditorField, MultiSelectField } from "../forms";

type ClassValue = string | false | null | undefined;

const classNames = (...values: ClassValue[]): string =>
  values.filter(Boolean).join(" ");

export interface TransitionNarrationOverridesEditorProps {
  readonly overrides: readonly NarrationOverrideResource[];
  readonly historyOptions: readonly string[];
  readonly itemOptions: readonly string[];
  readonly disabled?: boolean;
  readonly onChange: (
    overrides: readonly NarrationOverrideResource[],
  ) => void;
}

const buildOverrideKey = (
  override: NarrationOverrideResource,
  index: number,
): string => {
  if (override.records && override.records.length > 0) {
    return `${index}-${override.records.join("-")}`;
  }
  if (override.requires_history_all && override.requires_history_all.length > 0) {
    return `${index}-${override.requires_history_all.join("-")}`;
  }
  if (override.requires_history_any && override.requires_history_any.length > 0) {
    return `${index}-${override.requires_history_any.join("-")}`;
  }
  return `${index}-${override.narration.slice(0, 12)}`;
};

export const TransitionNarrationOverridesEditor: React.FC<
  TransitionNarrationOverridesEditorProps
> = ({
  overrides,
  historyOptions,
  itemOptions,
  disabled = false,
  onChange,
}) => {
  const hasOverrides = overrides.length > 0;

  const handleOverrideChange = React.useCallback(
    (index: number, nextOverride: NarrationOverrideResource) => {
      onChange(
        overrides.map((override, overrideIndex) =>
          overrideIndex === index ? nextOverride : override,
        ),
      );
    },
    [onChange, overrides],
  );

  const handleRemoveOverride = React.useCallback(
    (index: number) => {
      onChange(overrides.filter((_, overrideIndex) => overrideIndex !== index));
    },
    [onChange, overrides],
  );

  const handleAddOverride = React.useCallback(() => {
    onChange([
      ...overrides,
      {
        narration: "",
        requires_history_any: [],
        requires_history_all: [],
        records: [],
      },
    ]);
  }, [onChange, overrides]);

  return (
    <Card
      variant="subtle"
      title="Conditional narration overrides"
      description="Craft alternate narration for players who meet specific history milestones."
      actions={
        <button
          type="button"
          onClick={handleAddOverride}
          disabled={disabled}
          className={classNames(
            "inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs font-semibold uppercase tracking-wide transition",
            disabled
              ? "cursor-not-allowed border-slate-700/60 text-slate-500"
              : "border-indigo-400/60 text-indigo-100 hover:border-indigo-300 hover:bg-indigo-500/10",
          )}
        >
          Add override
        </button>
      }
    >
      {!hasOverrides ? (
        <p className="text-sm text-slate-300">
          No conditional narration configured yet. Add an override to tailor
          the story for specific player history combinations.
        </p>
      ) : null}
      <ul className="flex flex-col gap-4">
        {overrides.map((override, index) => {
          const key = buildOverrideKey(override, index);
          const historyAll = override.requires_history_all ?? [];
          const historyAny = override.requires_history_any ?? [];
          const forbidsHistoryAny = override.forbids_history_any ?? [];
          const inventoryAll = override.requires_inventory_all ?? [];
          const inventoryAny = override.requires_inventory_any ?? [];
          const forbidsInventoryAny =
            override.forbids_inventory_any ?? [];

          return (
            <li
              key={key}
              className="rounded-lg border border-slate-800/70 bg-slate-950/40 p-4 shadow-inner shadow-slate-950/20"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex flex-col gap-1">
                  <h4 className="text-sm font-semibold text-slate-200">
                    Override {index + 1}
                  </h4>
                  <p className="text-xs text-slate-400">
                    Configure the history requirements and narration players
                    will see when those conditions are satisfied.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => handleRemoveOverride(index)}
                  disabled={disabled}
                  className={classNames(
                    "inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[11px] font-semibold uppercase tracking-wide transition",
                    disabled
                      ? "cursor-not-allowed border-slate-800/70 text-slate-600"
                      : "border-red-500/50 text-red-200 hover:border-red-400 hover:bg-red-500/10",
                  )}
                >
                  Remove
                </button>
              </div>
              <div className="mt-4 grid gap-4 lg:grid-cols-2">
                <MarkdownEditorField
                  className="lg:col-span-1"
                  label="Override narration"
                  value={override.narration ?? ""}
                  onChange={(nextValue) =>
                    handleOverrideChange(index, {
                      ...override,
                      narration: nextValue,
                    })
                  }
                  placeholder="Describe the alternate outcome for players who satisfy these history requirements."
                  disabled={disabled}
                  minHeight={180}
                />
                <div className="flex flex-col gap-4 lg:col-span-1">
                  <MultiSelectField
                    label="History required (all)"
                    description="Players must have recorded every listed history entry to see this narration."
                    values={historyAll}
                    onChange={(values) =>
                      handleOverrideChange(index, {
                        ...override,
                        requires_history_all: values,
                      })
                    }
                    options={historyOptions}
                    placeholder="Add required history entries"
                    disabled={disabled}
                  />
                  <MultiSelectField
                    label="History required (any)"
                    description="Players need at least one of these history entries for the override to apply."
                    values={historyAny}
                    onChange={(values) =>
                      handleOverrideChange(index, {
                        ...override,
                        requires_history_any: values,
                      })
                    }
                    options={historyOptions}
                    placeholder="Add optional history entries"
                    disabled={disabled}
                  />
                  <MultiSelectField
                    label="Forbidden history entries"
                    description="Players must not have any of these history records for the override to apply."
                    values={forbidsHistoryAny}
                    onChange={(values) =>
                      handleOverrideChange(index, {
                        ...override,
                        forbids_history_any: values,
                      })
                    }
                    options={historyOptions}
                    placeholder="Add forbidden history entries"
                    disabled={disabled}
                  />
                  <MultiSelectField
                    label="Inventory required (all)"
                    description="Players must carry every listed item to unlock this narration."
                    values={inventoryAll}
                    onChange={(values) =>
                      handleOverrideChange(index, {
                        ...override,
                        requires_inventory_all: values,
                      })
                    }
                    options={itemOptions}
                    placeholder="Add required items"
                    disabled={disabled}
                  />
                  <MultiSelectField
                    label="Inventory required (any)"
                    description="Players need at least one of these items for the override to apply."
                    values={inventoryAny}
                    onChange={(values) =>
                      handleOverrideChange(index, {
                        ...override,
                        requires_inventory_any: values,
                      })
                    }
                    options={itemOptions}
                    placeholder="Add optional items"
                    disabled={disabled}
                  />
                  <MultiSelectField
                    label="Forbidden inventory"
                    description="The override is hidden if players carry any of these items."
                    values={forbidsInventoryAny}
                    onChange={(values) =>
                      handleOverrideChange(index, {
                        ...override,
                        forbids_inventory_any: values,
                      })
                    }
                    options={itemOptions}
                    placeholder="Add forbidden items"
                    disabled={disabled}
                  />
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </Card>
  );
};

TransitionNarrationOverridesEditor.displayName =
  "TransitionNarrationOverridesEditor";

