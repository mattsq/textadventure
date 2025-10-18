import React from "react";
import type {
  NarrationOverrideResource,
  SceneCommentThreadResource,
  TransitionResource,
} from "../../api";
import { Card } from "../display";
import { SceneCommentThreadPanel } from "../collaboration";
import {
  AutocompleteField,
  MarkdownEditorField,
  MultiSelectField,
} from "../forms";
import type { ChoiceEditorItem } from "./ChoiceListEditor";
import { TransitionNarrationOverridesEditor } from "./TransitionNarrationOverridesEditor";

type ClassValue = string | false | null | undefined;

const classNames = (...values: ClassValue[]): string =>
  values.filter(Boolean).join(" ");

export type TransitionExtras = Omit<TransitionResource, "target" | "narration">;

export interface TransitionEditorValues {
  readonly target: string | null;
  readonly narration: string;
  readonly extras: TransitionExtras;
}

export interface TransitionCommentSupport {
  readonly status: "idle" | "loading" | "ready" | "error" | "disabled";
  readonly threadsByCommand: Record<
    string,
    readonly SceneCommentThreadResource[]
  >;
  readonly error?: string | null;
  readonly disabledReason?: string | null;
  readonly onRefresh?: () => void | Promise<void>;
  readonly onCreateThread?: (command: string, body: string) => Promise<void>;
  readonly onReply?: (
    command: string,
    threadId: string,
    body: string,
  ) => Promise<void>;
  readonly onResolve?: (
    command: string,
    threadId: string,
    resolved: boolean,
  ) => Promise<void>;
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
  readonly historyOptions: readonly string[];
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
  readonly onNarrationOverridesChange: (
    choiceKey: string,
    overrides: readonly NarrationOverrideResource[],
  ) => void;
  readonly highlightedChoiceKey?: string | null;
  readonly getItemRef?: (choiceKey: string) => (element: HTMLLIElement | null) => void;
  readonly commentSupport?: TransitionCommentSupport;
}

export const TransitionListEditor: React.FC<TransitionListEditorProps> = ({
  className,
  choices,
  transitions,
  errors,
  targetOptions,
  itemOptions,
  historyOptions,
  disabled = false,
  onTargetChange,
  onNarrationChange,
  onFailureNarrationChange,
  onRequiresChange,
  onConsumesChange,
  onNarrationOverridesChange,
  highlightedChoiceKey = null,
  getItemRef,
  commentSupport,
}) => {
  const [expandedCommentChoiceKey, setExpandedCommentChoiceKey] =
    React.useState<string | null>(null);

  React.useEffect(() => {
    if (!commentSupport) {
      setExpandedCommentChoiceKey(null);
      return;
    }

    if (!expandedCommentChoiceKey) {
      return;
    }

    const targetChoice = choices.find((choice) => choice.key === expandedCommentChoiceKey);
    if (!targetChoice) {
      setExpandedCommentChoiceKey(null);
      return;
    }

    if (!targetChoice.command.trim()) {
      setExpandedCommentChoiceKey(null);
    }
  }, [commentSupport, choices, expandedCommentChoiceKey]);

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
              const trimmedCommand = choice.command.trim();
              const commentThreads =
                trimmedCommand && commentSupport
                  ? commentSupport.threadsByCommand[trimmedCommand] ?? []
                  : [];
              const totalThreadCount = commentThreads.length;
              const openThreadCount = commentThreads.filter(
                (thread) => thread.status === "open",
              ).length;
              const hasOpenThreads = openThreadCount > 0;
              const commentButtonDisabled =
                !commentSupport ||
                !trimmedCommand ||
                commentSupport.status === "disabled" ||
                commentSupport.status === "idle";
              const isCommentExpanded =
                expandedCommentChoiceKey === choice.key;
              const commentPanelId = `transition-comment-panel-${choice.key}`;
              const commentButtonClassName = classNames(
                "inline-flex items-center gap-2 rounded-md border px-2 py-1 text-xs font-semibold transition",
                commentButtonDisabled
                  ? "cursor-not-allowed border-slate-800 text-slate-500"
                  : hasOpenThreads
                    ? "border-amber-400/60 text-amber-200 hover:bg-amber-500/20"
                    : "border-slate-700/60 text-slate-300 hover:border-indigo-400/60 hover:text-indigo-100",
              );

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
                        labelActions={
                          commentSupport ? (
                            <button
                              type="button"
                              onClick={() => {
                                if (commentButtonDisabled) {
                                  return;
                                }
                                setExpandedCommentChoiceKey((previous) =>
                                  previous === choice.key ? null : choice.key,
                                );
                              }}
                              disabled={commentButtonDisabled}
                              aria-expanded={isCommentExpanded}
                              aria-controls={commentPanelId}
                              className={commentButtonClassName}
                            >
                              <span>Comments</span>
                              {hasOpenThreads ? (
                                <span className="rounded-full bg-amber-500/20 px-1.5 text-[10px] font-semibold uppercase tracking-wide text-amber-100">
                                  {openThreadCount} open
                                </span>
                              ) : null}
                              {totalThreadCount > 0 ? (
                                <span className="inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-indigo-500/30 px-1 text-[10px] font-semibold text-indigo-100">
                                  {totalThreadCount}
                                </span>
                              ) : null}
                            </button>
                          ) : undefined
                        }
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
                      {isCommentExpanded && commentSupport ? (
                        <div className="md:col-span-2" id={commentPanelId}>
                          <SceneCommentThreadPanel
                            status={commentSupport.status}
                            threads={commentThreads}
                            error={commentSupport.error ?? null}
                            disabledReason={commentSupport.disabledReason ?? null}
                            onRefresh={
                              commentSupport.onRefresh
                                ? () => commentSupport.onRefresh?.()
                                : undefined
                            }
                            onCreateThread={
                              commentSupport.onCreateThread && trimmedCommand
                                ? (body) =>
                                    commentSupport.onCreateThread!(
                                      trimmedCommand,
                                      body,
                                    )
                                : undefined
                            }
                            onReply={
                              commentSupport.onReply && trimmedCommand
                                ? (threadId, body) =>
                                    commentSupport.onReply!(
                                      trimmedCommand,
                                      threadId,
                                      body,
                                    )
                                : undefined
                            }
                            onResolve={
                              commentSupport.onResolve && trimmedCommand
                                ? (threadId, resolved) =>
                                    commentSupport.onResolve!(
                                      trimmedCommand,
                                      threadId,
                                      resolved,
                                    )
                                : undefined
                            }
                          />
                        </div>
                      ) : null}
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
                      <TransitionNarrationOverridesEditor
                        overrides={
                          transition?.extras?.narration_overrides ?? []
                        }
                        historyOptions={historyOptions}
                        itemOptions={itemOptions}
                        disabled={disabled}
                        onChange={(overrides) =>
                          onNarrationOverridesChange(choice.key, overrides)
                        }
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
