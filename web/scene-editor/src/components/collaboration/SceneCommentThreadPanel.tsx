import React from "react";
import MDEditor from "@uiw/react-md-editor";
import remarkGfm from "remark-gfm";

import {
  SceneEditorApiError,
  type SceneCommentThreadResource,
} from "../../api";
import { Badge } from "../display";

const statusBadgeVariant: Record<
  SceneCommentThreadResource["status"],
  React.ComponentProps<typeof Badge>["variant"]
> = {
  open: "info",
  resolved: "success",
};

const formatTimestamp = (value: string): string => {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
};

const formatErrorMessage = (error: unknown): string => {
  if (error instanceof SceneEditorApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Something went wrong while updating the comment thread.";
};

export interface SceneCommentThreadPanelProps {
  readonly status: "idle" | "loading" | "ready" | "error" | "disabled";
  readonly threads: readonly SceneCommentThreadResource[];
  readonly error?: string | null;
  readonly disabledReason?: string | null;
  readonly onRefresh?: () => void | Promise<void>;
  readonly onCreateThread?: (body: string) => Promise<void>;
  readonly onReply?: (threadId: string, body: string) => Promise<void>;
  readonly onResolve?: (threadId: string, resolved: boolean) => Promise<void>;
}

export const SceneCommentThreadPanel: React.FC<SceneCommentThreadPanelProps> = ({
  status,
  threads,
  error,
  disabledReason,
  onRefresh,
  onCreateThread,
  onReply,
  onResolve,
}) => {
  const [newThreadBody, setNewThreadBody] = React.useState("");
  const [replyDrafts, setReplyDrafts] = React.useState<Record<string, string>>({});
  const [localError, setLocalError] = React.useState<string | null>(null);
  const [pendingAction, setPendingAction] = React.useState<string | null>(null);

  React.useEffect(() => {
    setLocalError(null);
  }, [status, error]);

  const isDisabled = status === "disabled";
  const displayedError = error ?? localError;

  const handleCreateThread = async (
    event: React.FormEvent<HTMLFormElement>,
  ): Promise<void> => {
    event.preventDefault();
    if (!onCreateThread) {
      return;
    }
    const trimmed = newThreadBody.trim();
    if (!trimmed) {
      setLocalError("Enter a comment before starting a thread.");
      return;
    }

    setPendingAction("create");
    setLocalError(null);
    try {
      await onCreateThread(trimmed);
      setNewThreadBody("");
    } catch (cause) {
      setLocalError(formatErrorMessage(cause));
    } finally {
      setPendingAction(null);
    }
  };

  const handleReplySubmit = async (
    event: React.FormEvent<HTMLFormElement>,
    threadId: string,
  ): Promise<void> => {
    event.preventDefault();
    if (!onReply) {
      return;
    }
    const body = replyDrafts[threadId] ?? "";
    const trimmed = body.trim();
    if (!trimmed) {
      setLocalError("Enter a comment before posting a reply.");
      return;
    }

    setPendingAction(`reply:${threadId}`);
    setLocalError(null);
    try {
      await onReply(threadId, trimmed);
      setReplyDrafts((previous) => {
        const next = { ...previous };
        delete next[threadId];
        return next;
      });
    } catch (cause) {
      setLocalError(formatErrorMessage(cause));
    } finally {
      setPendingAction(null);
    }
  };

  const handleResolveToggle = async (
    threadId: string,
    resolved: boolean,
  ): Promise<void> => {
    if (!onResolve) {
      return;
    }

    setPendingAction(`resolve:${threadId}`);
    setLocalError(null);
    try {
      await onResolve(threadId, resolved);
    } catch (cause) {
      setLocalError(formatErrorMessage(cause));
    } finally {
      setPendingAction(null);
    }
  };

  if (isDisabled) {
    return (
      <div className="rounded-lg border border-slate-800/60 bg-slate-900/40 px-4 py-3 text-sm text-slate-300">
        {disabledReason ?? "Inline comments are not available for this project."}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {status === "loading" || status === "idle" ? (
        <div className="text-sm text-slate-300">Loading comments…</div>
      ) : null}

      {displayedError ? (
        <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-100" role="alert">
          <p>{displayedError}</p>
          {onRefresh ? (
            <button
              type="button"
              onClick={() => {
                void onRefresh();
              }}
              className="mt-2 inline-flex items-center justify-center rounded-md border border-rose-400/60 px-3 py-1.5 text-xs font-semibold text-rose-100 transition hover:bg-rose-500/20"
            >
              Try again
            </button>
          ) : null}
        </div>
      ) : null}

      {threads.length === 0 && status === "ready" ? (
        <p className="text-sm text-slate-300">
          No comments yet. Start a thread to gather feedback on this narration.
        </p>
      ) : null}

      {threads.length > 0 ? (
        <ul className="flex flex-col gap-3">
          {threads.map((thread) => {
            const replyDraft = replyDrafts[thread.id] ?? "";
            const isResolving = pendingAction === `resolve:${thread.id}`;
            const isReplying = pendingAction === `reply:${thread.id}`;

            return (
              <li
                key={thread.id}
                className="rounded-lg border border-slate-800/70 bg-slate-900/60 p-4 shadow-inner shadow-slate-950/20"
              >
                <div className="flex flex-col gap-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <Badge variant={statusBadgeVariant[thread.status]}>{
                        thread.status === "resolved" ? "Resolved" : "Open"
                      }</Badge>
                      <span className="text-xs text-slate-400">
                        Updated {formatTimestamp(thread.updated_at)}
                      </span>
                    </div>
                    {onResolve ? (
                      <button
                        type="button"
                        onClick={() => {
                          void handleResolveToggle(
                            thread.id,
                            thread.status !== "resolved",
                          );
                        }}
                        disabled={isResolving}
                        className="inline-flex items-center justify-center rounded-md border border-indigo-400/60 px-3 py-1.5 text-xs font-semibold text-indigo-100 transition hover:bg-indigo-500/20 disabled:cursor-not-allowed disabled:border-slate-800 disabled:text-slate-500"
                      >
                        {thread.status === "resolved"
                          ? isResolving
                            ? "Reopening…"
                            : "Reopen thread"
                          : isResolving
                          ? "Resolving…"
                          : "Mark as resolved"}
                      </button>
                    ) : null}
                  </div>

                  <ul className="flex flex-col gap-2">
                    {thread.comments.map((comment) => {
                      const authorLabel =
                        comment.author_display_name ||
                        comment.author_id ||
                        "Anonymous collaborator";

                      return (
                        <li
                          key={comment.id}
                          className="rounded-md border border-slate-800/60 bg-slate-900/70 px-3 py-2"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <span className="text-sm font-semibold text-slate-200">
                              {authorLabel}
                            </span>
                            <span className="text-xs text-slate-400">
                              {formatTimestamp(comment.created_at)}
                            </span>
                          </div>
                          <div className="prose prose-invert mt-2 max-w-none text-sm">
                            <MDEditor.Markdown source={comment.body} remarkPlugins={[remarkGfm]} />
                          </div>
                        </li>
                      );
                    })}
                  </ul>

                  {onReply ? (
                    <form
                      className="mt-2 flex flex-col gap-2"
                      onSubmit={(event) => void handleReplySubmit(event, thread.id)}
                    >
                      <label htmlFor={`${thread.id}-reply`} className="text-xs font-semibold uppercase tracking-wide text-slate-300">
                        Add a reply
                      </label>
                      <textarea
                        id={`${thread.id}-reply`}
                        value={replyDraft}
                        onChange={(event) =>
                          setReplyDrafts((previous) => ({
                            ...previous,
                            [thread.id]: event.target.value,
                          }))
                        }
                        className="min-h-[96px] w-full rounded-md border border-slate-800/70 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                        placeholder="Share your feedback or ask a follow-up question."
                        disabled={isReplying}
                        required
                      />
                      <div className="flex items-center gap-2">
                        <button
                          type="submit"
                          className="inline-flex items-center justify-center rounded-md border border-indigo-400/60 bg-indigo-500/30 px-3 py-1.5 text-xs font-semibold text-indigo-100 transition hover:bg-indigo-500/40 disabled:cursor-not-allowed disabled:border-slate-800 disabled:bg-slate-900/40 disabled:text-slate-500"
                          disabled={isReplying}
                        >
                          {isReplying ? "Posting…" : "Post reply"}
                        </button>
                        <button
                          type="button"
                          onClick={() =>
                            setReplyDrafts((previous) => {
                              const next = { ...previous };
                              delete next[thread.id];
                              return next;
                            })
                          }
                          className="text-xs font-semibold text-slate-400 transition hover:text-slate-200"
                          disabled={isReplying || !replyDraft}
                        >
                          Clear
                        </button>
                      </div>
                    </form>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ul>
      ) : null}

      {onCreateThread ? (
        <form className="flex flex-col gap-2" onSubmit={handleCreateThread}>
          <label htmlFor="scene-comment-new" className="text-xs font-semibold uppercase tracking-wide text-slate-300">
            Start a new thread
          </label>
          <textarea
            id="scene-comment-new"
            value={newThreadBody}
            onChange={(event) => setNewThreadBody(event.target.value)}
            className="min-h-[120px] w-full rounded-md border border-slate-800/70 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
            placeholder="Outline your suggestion or question for collaborators."
            disabled={pendingAction === "create"}
            required
          />
          <div className="flex items-center gap-2">
            <button
              type="submit"
              className="inline-flex items-center justify-center rounded-md border border-indigo-400/60 bg-indigo-500/30 px-4 py-2 text-sm font-semibold text-indigo-100 transition hover:bg-indigo-500/40 disabled:cursor-not-allowed disabled:border-slate-800 disabled:bg-slate-900/40 disabled:text-slate-500"
              disabled={pendingAction === "create"}
            >
              {pendingAction === "create" ? "Starting…" : "Start thread"}
            </button>
            {onRefresh ? (
              <button
                type="button"
                onClick={() => {
                  void onRefresh();
                }}
                className="text-sm font-semibold text-slate-400 transition hover:text-slate-200"
              >
                Refresh
              </button>
            ) : null}
          </div>
        </form>
      ) : null}
    </div>
  );
};

SceneCommentThreadPanel.displayName = "SceneCommentThreadPanel";
