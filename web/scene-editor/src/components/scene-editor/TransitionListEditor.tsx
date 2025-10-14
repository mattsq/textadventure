import React from "react";
import type { TransitionResource } from "../../api";
import { Card } from "../display";
import {
  AutocompleteField,
  MarkdownEditorField,
  MultiSelectField,
} from "../forms";
import type { ChoiceEditorItem } from "./ChoiceListEditor";

type ClassValue = string | false | null | undefined;

const classNames = (...values: ClassValue[]): string =>
  values.filter(Boolean).join(" ");

export type TransitionExtras = Omit<TransitionResource, "target" | "narration">;

export interface TransitionEditorValues {
  readonly target: string | null;
  readonly narration: string;
  readonly extras: TransitionExtras;
}

export interface TransitionEditorFieldErrors {
  target?: string;
  narration?: string;
  requires?: string;
  consumes?: string;
  failureNarration?: string;
}

export interface TransitionListEditorProps {
  readonly className?: string;
  readonly choices: readonly ChoiceEditorItem[];
  readonly transitions: Readonly<Record<string, TransitionEditorValues>>;
  readonly errors: Readonly<Record<string, TransitionEditorFieldErrors>>;
  readonly targetOptions: readonly string[];
  readonly itemOptions: readonly string[];
  readonly disabled?: boolean;
  readonly onTargetChange: (choiceKey: string, value: string) => void;
  readonly onNarrationChange: (choiceKey: string, value: string) => void;
  readonly onFailureNarrationChange: (
    choiceKey: string,
    value: string,
  ) => void;
  readonly onRequiresChange: (
    choiceKey: string,
    values: readonly string[],
  ) => void;
  readonly onConsumesChange: (
    choiceKey: string,
    values: readonly string[],
  ) => void;
  readonly highlightedChoiceKey?: string | null;
  readonly getItemRef?: (choiceKey: string) => (element: HTMLLIElement | null) => void;
}

export const TransitionListEditor: React.FC<TransitionListEditorProps> = ({
  className,
  choices,
  transitions,
  errors,
  targetOptions,
  itemOptions,
  disabled = false,
  onTargetChange,
  onNarrationChange,
  onFailureNarrationChange,
  onRequiresChange,
  onConsumesChange,
  highlightedChoiceKey = null,
  getItemRef,
}) => {
  return (
    <div className={classNames("flex flex-col gap-4", className)}>
      <Card
        variant="subtle"
        title="Scene transitions"
        description="Wire each player choice to a destination scene or mark it as a terminal outcome with custom narration."
      >
        {choices.length === 0 ? (
          <p className="text-slate-300">
            Add at least one choice before configuring transitions. Each choice
            can lead to another scene or end the adventure.
          </p>
        ) : (
          <ul className="flex flex-col gap-4">
            {choices.map((choice, index) => {
              const transition = transitions[choice.key];
              const fieldErrors = errors[choice.key] ?? {};
              const datalistId = `transition-targets-${choice.key}`;
              const isHighlighted = highlightedChoiceKey === choice.key;
              const requiresValues = transition?.extras?.requires ?? [];
              const consumesValues = transition?.extras?.consumes ?? [];
              const failureNarration =
                transition?.extras?.failure_narration ?? "";

              return (
                <li
                  key={choice.key}
                  ref={getItemRef ? getItemRef(choice.key) : undefined}
                  className={classNames(
                    "rounded-xl border border-slate-800/60 bg-slate-900/40 p-4 shadow-inner shadow-slate-950/20 transition",
                    isHighlighted
                      ? "border-indigo-400/80 shadow-indigo-500/30 ring-2 ring-indigo-400/60"
                      : undefined,
                  )}
                  tabIndex={isHighlighted ? -1 : undefined}
                  data-highlighted={isHighlighted || undefined}
                >
                  <div className="flex flex-col gap-3">
                    <div className="flex flex-col gap-1">
                      <h4 className="text-sm font-semibold uppercase tracking-wide text-slate-300">
                        Transition {index + 1}: {choice.command || "(untitled command)"}
                      </h4>
                      <p className="text-xs text-slate-500">
                        Specify the destination scene ID or leave blank to mark
                        this choice as an ending. Provide narration so players
                        understand the outcome.
                      </p>
                    </div>
                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="flex flex-col gap-2 md:col-span-1">
                        <AutocompleteField
                          label="Target scene"
                          value={transition?.target ?? ""}
                          onValueChange={(nextValue) =>
                            onTargetChange(choice.key, nextValue)
                          }
                          placeholder="Search for a destination scene"
                          description="Start typing to filter known scene IDs. Leave empty to end the scene."
                          disabled={disabled}
                          options={targetOptions}
                          error={fieldErrors.target}
                          id={datalistId}
                        />
                      </div>
                      <MarkdownEditorField
                        className="md:col-span-1"
                        label="Transition narration"
                        value={transition?.narration ?? ""}
                        onChange={(nextValue) =>
                          onNarrationChange(choice.key, nextValue)
                        }
                        placeholder="Describe what happens after the player selects this choice."
                        required
                        disabled={disabled}
                        error={fieldErrors.narration}
                        previewMode="live"
                        minHeight={220}
                      />
                      <MarkdownEditorField
                        className="md:col-span-2"
                        label="Failure narration"
                        description="Shown when the player lacks the requirements needed to trigger this transition."
                        value={failureNarration}
                        onChange={(nextValue) =>
                          onFailureNarrationChange(choice.key, nextValue)
                        }
                        placeholder="Explain what happens when requirements are not met so players know what's missing."
                        disabled={disabled}
                        error={fieldErrors.failureNarration}
                        previewMode="live"
                        minHeight={200}
                      />
                      <MultiSelectField
                        className="md:col-span-2"
                        label="Required items"
                        description="List the inventory items a player must carry to trigger this transition. Type to add a new requirement or pick from existing items."
                        values={requiresValues}
                        onChange={(nextValues: readonly string[]) =>
                          onRequiresChange(choice.key, nextValues)
                        }
                        options={itemOptions}
                        placeholder="Add required items"
                        disabled={disabled}
                        error={fieldErrors.requires}
                      />
                      <MultiSelectField
                        className="md:col-span-2"
                        label="Consumed items"
                        description="List the items that are removed from the player's inventory when this transition fires. Type to add a new consumption rule or pick from existing items."
                        values={consumesValues}
                        onChange={(nextValues: readonly string[]) =>
                          onConsumesChange(choice.key, nextValues)
                        }
                        options={itemOptions}
                        placeholder="Add consumed items"
                        disabled={disabled}
                        error={fieldErrors.consumes}
                      />
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Card>
    </div>
  );
};

export default TransitionListEditor;
