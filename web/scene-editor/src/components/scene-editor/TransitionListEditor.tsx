import React from "react";
import type { TransitionResource } from "../../api";
import { Card } from "../display";
import { TextAreaField, TextField } from "../forms";
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
}

interface TransitionListItemProps {
  readonly choice: ChoiceEditorItem;
  readonly index: number;
  readonly transition: TransitionEditorValues | undefined;
  readonly fieldErrors: TransitionEditorFieldErrors;
  readonly targetOptions: readonly string[];
  readonly disabled: boolean;
  readonly isFocused: boolean;
  readonly onTargetChange: (choiceKey: string, value: string) => void;
  readonly onNarrationChange: (choiceKey: string, value: string) => void;
}

const TransitionListItem: React.FC<TransitionListItemProps> = ({
  choice,
  index,
  transition,
  fieldErrors,
  targetOptions,
  disabled,
  isFocused,
  onTargetChange,
  onNarrationChange,
}) => {
  const itemRef = React.useRef<HTMLLIElement | null>(null);

  React.useEffect(() => {
    if (isFocused && itemRef.current) {
      itemRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [isFocused]);

  const datalistId = `transition-targets-${choice.key}`;

  return (
    <li
      ref={itemRef}
      tabIndex={-1}
      data-command={choice.command}
      className={classNames(
        "rounded-xl border border-slate-800/60 bg-slate-900/40 p-4 shadow-inner shadow-slate-950/20 outline-none transition",
        "focus-visible:ring-2 focus-visible:ring-indigo-400/60",
        isFocused &&
          "border-indigo-400/70 bg-indigo-500/10 shadow-lg shadow-indigo-900/30 ring-2 ring-indigo-400/40",
      )}
    >
      <div className="flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <h4 className="text-sm font-semibold uppercase tracking-wide text-slate-300">
            Transition {index + 1}: {choice.command || "(untitled command)"}
          </h4>
          <p className="text-xs text-slate-500">
            Specify the destination scene ID or leave blank to mark this choice
            as an ending. Provide narration so players understand the outcome.
          </p>
          {isFocused ? (
            <p className="text-xs font-semibold uppercase tracking-wide text-indigo-200">
              Selected from scene graph
            </p>
          ) : null}
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="flex flex-col gap-2 md:col-span-1">
            <TextField
              label="Target scene"
              value={transition?.target ?? ""}
              onChange={(event) => onTargetChange(choice.key, event.target.value)}
              placeholder="next-scene-id"
              description="Suggestions include known scene IDs. Leave empty to end the scene."
              disabled={disabled}
              list={targetOptions.length > 0 ? datalistId : undefined}
              error={fieldErrors.target}
            />
            {targetOptions.length > 0 ? (
              <datalist id={datalistId}>
                {targetOptions.map((sceneId) => (
                  <option key={sceneId} value={sceneId} />
                ))}
              </datalist>
            ) : null}
          </div>
          <TextAreaField
            className="md:col-span-1"
            label="Transition narration"
            value={transition?.narration ?? ""}
            onChange={(event) => onNarrationChange(choice.key, event.target.value)}
            placeholder="Describe what happens after the player selects this choice."
            rows={4}
            required
            disabled={disabled}
            error={fieldErrors.narration}
          />
        </div>
      </div>
    </li>
  );
};

export interface TransitionListEditorProps {
  readonly className?: string;
  readonly choices: readonly ChoiceEditorItem[];
  readonly transitions: Readonly<Record<string, TransitionEditorValues>>;
  readonly errors: Readonly<Record<string, TransitionEditorFieldErrors>>;
  readonly targetOptions: readonly string[];
  readonly disabled?: boolean;
  readonly focusedCommand?: string | null;
  readonly onTargetChange: (choiceKey: string, value: string) => void;
  readonly onNarrationChange: (choiceKey: string, value: string) => void;
}

export const TransitionListEditor: React.FC<TransitionListEditorProps> = ({
  className,
  choices,
  transitions,
  errors,
  targetOptions,
  disabled = false,
  focusedCommand = null,
  onTargetChange,
  onNarrationChange,
}) => {
  const normalisedFocusedCommand = React.useMemo(() => {
    const trimmed = focusedCommand?.trim();
    return trimmed && trimmed.length > 0 ? trimmed : null;
  }, [focusedCommand]);

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
              const normalisedChoiceCommand = choice.command.trim();
              const isFocused =
                normalisedFocusedCommand !== null &&
                normalisedChoiceCommand !== "" &&
                normalisedChoiceCommand === normalisedFocusedCommand;

              return (
                <TransitionListItem
                  key={choice.key}
                  choice={choice}
                  index={index}
                  transition={transition}
                  fieldErrors={fieldErrors}
                  targetOptions={targetOptions}
                  disabled={disabled}
                  isFocused={isFocused}
                  onTargetChange={onTargetChange}
                  onNarrationChange={onNarrationChange}
                />
              );
            })}
          </ul>
        )}
      </Card>
    </div>
  );
};

export default TransitionListEditor;
