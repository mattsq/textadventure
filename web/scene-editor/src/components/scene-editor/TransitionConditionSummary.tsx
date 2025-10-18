import React from "react";
import type { NarrationOverrideResource } from "../../api";
import { Badge, type BadgeVariant } from "../display";
import type { TransitionExtras } from "./TransitionListEditor";

interface TransitionConditionSummaryProps {
  readonly target: string | null | undefined;
  readonly extras?: TransitionExtras;
  readonly className?: string;
}

type ClassValue = string | false | null | undefined;

const classNames = (...values: readonly ClassValue[]): string =>
  values.filter(Boolean).join(" ");

const normaliseList = (
  values?: readonly string[] | null,
): readonly string[] => {
  if (!values) {
    return [];
  }

  const result = new Set<string>();
  for (const value of values) {
    const trimmed = typeof value === "string" ? value.trim() : "";
    if (!trimmed) {
      continue;
    }
    result.add(trimmed);
  }

  return Array.from(result).sort((a, b) => a.localeCompare(b));
};

const formatList = (values: readonly string[]): string => {
  if (values.length === 0) {
    return "";
  }

  if (values.length === 1) {
    return values[0];
  }

  if (values.length === 2) {
    return `${values[0]} and ${values[1]}`;
  }

  const [, ...rest] = values;
  return `${values[0]}, ${rest.slice(0, -1).join(", ")}, and ${rest[rest.length - 1]}`;
};

interface OverrideConditionSummary {
  readonly historyAll: readonly string[];
  readonly historyAny: readonly string[];
  readonly historyForbidden: readonly string[];
  readonly inventoryAll: readonly string[];
  readonly inventoryAny: readonly string[];
  readonly inventoryForbidden: readonly string[];
  readonly records: readonly string[];
}

const buildOverrideConditionSummary = (
  overrides: readonly NarrationOverrideResource[] | undefined,
): OverrideConditionSummary => {
  const historyAll = new Set<string>();
  const historyAny = new Set<string>();
  const historyForbidden = new Set<string>();
  const inventoryAll = new Set<string>();
  const inventoryAny = new Set<string>();
  const inventoryForbidden = new Set<string>();
  const records = new Set<string>();

  if (overrides) {
    for (const override of overrides) {
      normaliseList(override.requires_history_all).forEach((value) =>
        historyAll.add(value),
      );
      normaliseList(override.requires_history_any).forEach((value) =>
        historyAny.add(value),
      );
      normaliseList(override.forbids_history_any).forEach((value) =>
        historyForbidden.add(value),
      );
      normaliseList(override.requires_inventory_all).forEach((value) =>
        inventoryAll.add(value),
      );
      normaliseList(override.requires_inventory_any).forEach((value) =>
        inventoryAny.add(value),
      );
      normaliseList(override.forbids_inventory_any).forEach((value) =>
        inventoryForbidden.add(value),
      );
      normaliseList(override.records).forEach((value) => records.add(value));
    }
  }

  const toArray = (set: ReadonlySet<string>): readonly string[] =>
    Array.from(set).sort((a, b) => a.localeCompare(b));

  return {
    historyAll: toArray(historyAll),
    historyAny: toArray(historyAny),
    historyForbidden: toArray(historyForbidden),
    inventoryAll: toArray(inventoryAll),
    inventoryAny: toArray(inventoryAny),
    inventoryForbidden: toArray(inventoryForbidden),
    records: toArray(records),
  };
};

const buildAvailabilityBadge = (
  isTerminal: boolean,
  hasRequirements: boolean,
  hasOverrideConditions: boolean,
  grantsReward: boolean,
  overrideCount: number,
): { readonly label: string; readonly variant: BadgeVariant } => {
  if (isTerminal) {
    return { label: "Ending", variant: "danger" };
  }
  if (hasRequirements) {
    return { label: "Requires items", variant: "info" };
  }
  if (hasOverrideConditions) {
    return { label: "Conditional", variant: "info" };
  }
  if (grantsReward || overrideCount > 0) {
    return { label: "Special outcome", variant: "success" };
  }
  return { label: "Always available", variant: "neutral" };
};

export const TransitionConditionSummary: React.FC<
  TransitionConditionSummaryProps
> = ({ target, extras, className }) => {
  const normalisedTarget =
    typeof target === "string" ? target.trim() : target ?? null;
  const requires = normaliseList(extras?.requires ?? null);
  const consumes = normaliseList(extras?.consumes ?? null);
  const rewardItem = typeof extras?.item === "string" ? extras.item.trim() : "";
  const rewardItemValue = rewardItem.length > 0 ? rewardItem : null;
  const baseRecords = normaliseList(extras?.records ?? null);
  const failureNarration =
    typeof extras?.failure_narration === "string"
      ? extras.failure_narration.trim()
      : extras?.failure_narration ?? "";
  const hasFailureNarration = failureNarration.length > 0;
  const overrides = extras?.narration_overrides ?? [];
  const overrideCount = overrides.length;
  const overrideSummary = buildOverrideConditionSummary(overrides);

  const combinedRecords = (() => {
    if (overrideSummary.records.length === 0) {
      return baseRecords;
    }
    const result = new Set(baseRecords);
    for (const value of overrideSummary.records) {
      result.add(value);
    }
    return Array.from(result).sort((a, b) => a.localeCompare(b));
  })();

  const hasRequirements = requires.length > 0;
  const consumesItems = consumes.length > 0;
  const hasOverrideConditions =
    overrideSummary.historyAll.length > 0 ||
    overrideSummary.historyAny.length > 0 ||
    overrideSummary.historyForbidden.length > 0 ||
    overrideSummary.inventoryAll.length > 0 ||
    overrideSummary.inventoryAny.length > 0 ||
    overrideSummary.inventoryForbidden.length > 0;
  const grantsReward = Boolean(rewardItemValue) || combinedRecords.length > 0;
  const isTerminal = normalisedTarget === null || normalisedTarget === "";

  const availabilityBadge = buildAvailabilityBadge(
    isTerminal,
    hasRequirements,
    hasOverrideConditions,
    grantsReward,
    overrideCount,
  );

  const supplementaryBadges: Array<{
    readonly key: string;
    readonly label: string;
    readonly variant: BadgeVariant;
  }> = [];

  if (consumesItems) {
    supplementaryBadges.push({
      key: "consumes",
      label: "Consumes items",
      variant: "warning",
    });
  }
  if (rewardItemValue) {
    supplementaryBadges.push({
      key: "reward",
      label: "Grants item",
      variant: "success",
    });
  }
  if (combinedRecords.length > 0) {
    supplementaryBadges.push({
      key: "records",
      label: "Records history",
      variant: "success",
    });
  }
  if (overrideCount > 0) {
    supplementaryBadges.push({
      key: "overrides",
      label: `Overrides (${overrideCount})`,
      variant: "neutral",
    });
  }
  if (hasFailureNarration) {
    supplementaryBadges.push({
      key: "failure",
      label: "Failure text",
      variant: "danger",
    });
  }

  interface SummaryRow {
    readonly key: string;
    readonly label: string;
    readonly value: string;
  }

  const summaryRows: SummaryRow[] = [];

  if (hasRequirements) {
    summaryRows.push({
      key: "requires",
      label: "Required items",
      value: formatList(requires),
    });
  }

  if (consumesItems) {
    summaryRows.push({
      key: "consumes",
      label: "Consumed items",
      value: formatList(consumes),
    });
  }

  if (rewardItemValue) {
    summaryRows.push({
      key: "reward",
      label: "Grants item",
      value: rewardItemValue,
    });
  }

  if (combinedRecords.length > 0) {
    summaryRows.push({
      key: "records",
      label: "Records history",
      value: formatList(combinedRecords),
    });
  }

  if (overrideCount > 0) {
    summaryRows.push({
      key: "override-count",
      label: "Narration overrides",
      value: overrideCount === 1 ? "1 configured" : `${overrideCount} configured`,
    });
  }

  const overrideSegments: string[] = [];
  if (overrideSummary.historyAll.length > 0) {
    overrideSegments.push(
      `History (all): ${formatList(overrideSummary.historyAll)}`,
    );
  }
  if (overrideSummary.historyAny.length > 0) {
    overrideSegments.push(
      `History (any): ${formatList(overrideSummary.historyAny)}`,
    );
  }
  if (overrideSummary.historyForbidden.length > 0) {
    overrideSegments.push(
      `History (forbidden): ${formatList(overrideSummary.historyForbidden)}`,
    );
  }
  if (overrideSummary.inventoryAll.length > 0) {
    overrideSegments.push(
      `Inventory (all): ${formatList(overrideSummary.inventoryAll)}`,
    );
  }
  if (overrideSummary.inventoryAny.length > 0) {
    overrideSegments.push(
      `Inventory (any): ${formatList(overrideSummary.inventoryAny)}`,
    );
  }
  if (overrideSummary.inventoryForbidden.length > 0) {
    overrideSegments.push(
      `Inventory (forbidden): ${formatList(overrideSummary.inventoryForbidden)}`,
    );
  }

  if (overrideSegments.length > 0) {
    summaryRows.push({
      key: "override-conditions",
      label: "Override conditions",
      value: overrideSegments.join(" • "),
    });
  }

  if (hasFailureNarration) {
    summaryRows.push({
      key: "failure",
      label: "Failure narration",
      value: "Configured",
    });
  }

  if (summaryRows.length === 0) {
    summaryRows.push({
      key: "no-conditions",
      label: "Conditions",
      value: isTerminal
        ? "No additional requirements. Selecting this choice ends the adventure."
        : "No additional requirements. Available to all players.",
    });
  }

  return (
    <div
      className={classNames(
        "rounded-lg border border-slate-800/70 bg-slate-950/40 p-3",
        className,
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge size="sm" variant={availabilityBadge.variant}>
          {availabilityBadge.label}
        </Badge>
        {supplementaryBadges.map((badge) => (
          <Badge key={badge.key} size="sm" variant={badge.variant}>
            {badge.label}
          </Badge>
        ))}
      </div>
      <dl className="mt-3 grid gap-x-6 gap-y-2 text-xs text-slate-200 sm:grid-cols-2">
        {summaryRows.map((row) => (
          <div key={row.key} className="flex flex-col gap-0.5">
            <dt className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
              {row.label}
            </dt>
            <dd className="leading-relaxed text-slate-200">{row.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
};

TransitionConditionSummary.displayName = "TransitionConditionSummary";

export default TransitionConditionSummary;
