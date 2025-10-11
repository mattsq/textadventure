import React from "react";
import { Card } from "../display";
import { TextAreaField, TextField } from "../forms";

type ClassValue = string | false | null | undefined;

const classNames = (...values: ClassValue[]): string =>
  values.filter(Boolean).join(" ");

export interface ChoiceEditorItem {
  readonly key: string;
  readonly command: string;
  readonly description: string;
}

export interface ChoiceEditorFieldErrors {
  command?: string;
  description?: string;
}

export interface ChoiceListEditorProps {
  readonly className?: string;
  readonly choices: readonly ChoiceEditorItem[];
  readonly errors: Readonly<Record<string, ChoiceEditorFieldErrors>>;
  readonly disabled?: boolean;
  readonly onAddChoice: () => void;
  readonly onRemoveChoice: (choiceKey: string) => void;
  readonly onMoveChoice: (
    choiceKey: string,
    direction: "up" | "down",
  ) => void;
  readonly onChange: (
    choiceKey: string,
    field: "command" | "description",
    value: string,
  ) => void;
}

export const ChoiceListEditor: React.FC<ChoiceListEditorProps> = ({
  className,
  choices,
  errors,
  disabled = false,
  onAddChoice,
  onRemoveChoice,
  onMoveChoice,
  onChange,
}) => {
  return (
    <div className={classNames("flex flex-col gap-4", className)}>
      <Card
        variant="subtle"
        title="Scene choices"
        description="Manage the player commands and short descriptions that appear in this scene."
        actions={
          <button
            type="button"
            onClick={onAddChoice}
            disabled={disabled}
            className="rounded-md border border-indigo-500/50 bg-indigo-500/20 px-3 py-1.5 text-sm font-semibold text-indigo-100 shadow transition hover:bg-indigo-500/30 disabled:cursor-not-allowed disabled:border-slate-800 disabled:bg-slate-900/40 disabled:text-slate-500"
          >
            Add choice
          </button>
        }
      >
        {choices.length === 0 ? (
          <p className="text-slate-300">
            No choices configured yet. Add at least one command so players can pick their next move.
          </p>
        ) : (
          <ul className="flex flex-col gap-4">
            {choices.map((choice, index) => {
              const fieldErrors = errors[choice.key] ?? {};
              const isFirst = index === 0;
              const isLast = index === choices.length - 1;

              return (
                <li
                  key={choice.key}
                  className="rounded-xl border border-slate-800/60 bg-slate-900/40 p-4 shadow-inner shadow-slate-950/20"
                >
                  <div className="flex flex-col gap-3">
                    <div className="flex flex-col justify-between gap-3 md:flex-row md:items-center">
                      <div>
                        <h4 className="text-sm font-semibold uppercase tracking-wide text-slate-300">
                          Choice {index + 1}
                        </h4>
                        <p className="text-xs text-slate-500">
                          Configure the player command label and a short description.
                        </p>
                      </div>
                      <div className="flex flex-wrap items-center gap-2 text-xs font-semibold">
                        <button
                          type="button"
                          onClick={() => onMoveChoice(choice.key, "up")}
                          disabled={disabled || isFirst}
                          className="rounded-md border border-slate-800 bg-slate-900/60 px-3 py-1 text-slate-300 transition hover:border-indigo-400/60 hover:text-indigo-100 disabled:cursor-not-allowed disabled:border-slate-800 disabled:text-slate-600"
                        >
                          Move up
                        </button>
                        <button
                          type="button"
                          onClick={() => onMoveChoice(choice.key, "down")}
                          disabled={disabled || isLast}
                          className="rounded-md border border-slate-800 bg-slate-900/60 px-3 py-1 text-slate-300 transition hover:border-indigo-400/60 hover:text-indigo-100 disabled:cursor-not-allowed disabled:border-slate-800 disabled:text-slate-600"
                        >
                          Move down
                        </button>
                        <button
                          type="button"
                          onClick={() => onRemoveChoice(choice.key)}
                          disabled={disabled}
                          className="rounded-md border border-rose-500/60 bg-rose-500/10 px-3 py-1 text-rose-100 transition hover:bg-rose-500/20 disabled:cursor-not-allowed disabled:border-slate-800 disabled:bg-slate-900/40 disabled:text-slate-600"
                        >
                          Remove
                        </button>
                      </div>
                    </div>
                    <div className="grid gap-4 md:grid-cols-2">
                      <TextField
                        label="Command"
                        value={choice.command}
                        onChange={(event) =>
                          onChange(choice.key, "command", event.target.value)
                        }
                        placeholder="enter-command"
                        required
                        disabled={disabled}
                        error={fieldErrors.command}
                      />
                      <TextAreaField
                        label="Description"
                        value={choice.description}
                        onChange={(event) =>
                          onChange(choice.key, "description", event.target.value)
                        }
                        placeholder="What players see when browsing choices."
                        rows={3}
                        required
                        disabled={disabled}
                        error={fieldErrors.description}
                      />
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Card>

      {choices.length > 0 ? (
        <button
          type="button"
          onClick={onAddChoice}
          disabled={disabled}
          className="self-start rounded-md border border-indigo-500/50 bg-indigo-500/20 px-3 py-1.5 text-sm font-semibold text-indigo-100 shadow transition hover:bg-indigo-500/30 disabled:cursor-not-allowed disabled:border-slate-800 disabled:bg-slate-900/40 disabled:text-slate-500"
        >
          Add another choice
        </button>
      ) : null}
    </div>
  );
};

export default ChoiceListEditor;
