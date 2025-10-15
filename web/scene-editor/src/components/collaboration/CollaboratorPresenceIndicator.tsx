import React from "react";

import {
  createSceneEditorApiClient,
  SceneEditorApiError,
  type AdventureProjectListResponse,
  type ProjectCollaborationSessionResource,
} from "../../api";
import { Badge } from "../display";

type ClassValue = string | false | null | undefined;

const classNames = (...values: ClassValue[]): string =>
  values.filter(Boolean).join(" ");

const DEFAULT_POLL_INTERVAL_MS = 15000;

const roleLabels: Record<ProjectCollaborationSessionResource["role"], string> = {
  owner: "Owner",
  editor: "Editor",
  viewer: "Viewer",
};

const roleVariants: Record<ProjectCollaborationSessionResource["role"], React.ComponentProps<typeof Badge>["variant"]> = {
  owner: "success",
  editor: "info",
  viewer: "neutral",
};

type ProjectResolutionState =
  | { status: "idle" }
  | { status: "resolving" }
  | { status: "ready"; projectId: string; projectName: string | null }
  | { status: "empty" }
  | { status: "disabled"; message: string }
  | { status: "error"; message: string };

type PresenceStatus =
  | "idle"
  | "loading"
  | "ready"
  | "error"
  | "disabled";

interface PresenceState {
  readonly status: PresenceStatus;
  readonly projectId: string | null;
  readonly sessions: readonly ProjectCollaborationSessionResource[];
  readonly lastUpdatedAt: string | null;
  readonly error?: string;
}

const getInitials = (name: string): string => {
  const trimmed = name.trim();
  if (!trimmed) {
    return "?";
  }

  const parts = trimmed
    .split(/[^\p{L}\p{N}]+/u)
    .filter((part) => part.length > 0);

  if (parts.length === 0) {
    return trimmed.slice(0, 2).toUpperCase();
  }

  if (parts.length === 1) {
    const [single] = parts;
    return single.slice(0, 2).toUpperCase();
  }

  const first = parts[0]?.[0];
  const last = parts[parts.length - 1]?.[0];
  return `${first ?? ""}${last ?? ""}`.toUpperCase() || trimmed.slice(0, 2).toUpperCase();
};

const formatRelativeTime = (isoTimestamp: string | null): string => {
  if (!isoTimestamp) {
    return "just now";
  }

  const timestamp = new Date(isoTimestamp).getTime();
  if (Number.isNaN(timestamp)) {
    return "just now";
  }

  const diffMs = Date.now() - timestamp;
  if (diffMs <= 0) {
    return "just now";
  }

  const diffSeconds = Math.floor(diffMs / 1000);
  if (diffSeconds < 45) {
    return "moments ago";
  }

  if (diffSeconds < 90) {
    return "about a minute ago";
  }

  const diffMinutes = Math.floor(diffSeconds / 60);
  if (diffMinutes < 60) {
    return `${diffMinutes} minute${diffMinutes === 1 ? "" : "s"} ago`;
  }

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) {
    return `${diffHours} hour${diffHours === 1 ? "" : "s"} ago`;
  }

  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) {
    return `${diffDays} day${diffDays === 1 ? "" : "s"} ago`;
  }

  const diffWeeks = Math.floor(diffDays / 7);
  if (diffWeeks < 5) {
    return `${diffWeeks} week${diffWeeks === 1 ? "" : "s"} ago`;
  }

  const diffMonths = Math.floor(diffDays / 30);
  if (diffMonths < 12) {
    return `${diffMonths} month${diffMonths === 1 ? "" : "s"} ago`;
  }

  const diffYears = Math.floor(diffDays / 365);
  return `${diffYears} year${diffYears === 1 ? "" : "s"} ago`;
};

const describeSceneFocus = (
  session: ProjectCollaborationSessionResource,
  activeSceneId?: string,
): string => {
  if (!session.scene_id) {
    return "Exploring the project workspace";
  }

  if (activeSceneId && session.scene_id === activeSceneId) {
    return "Collaborating in this scene";
  }

  return `Editing scene "${session.scene_id}"`;
};

const formatExpiry = (isoTimestamp: string): string | null => {
  const timestamp = new Date(isoTimestamp).getTime();
  if (Number.isNaN(timestamp)) {
    return null;
  }

  const diffMs = timestamp - Date.now();
  if (diffMs <= 0) {
    return "expiring now";
  }

  const diffMinutes = Math.round(diffMs / 60000);
  if (diffMinutes < 1) {
    return "expiring shortly";
  }
  if (diffMinutes < 60) {
    return `expiring in ${diffMinutes} minute${diffMinutes === 1 ? "" : "s"}`;
  }

  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) {
    return `expiring in ${diffHours} hour${diffHours === 1 ? "" : "s"}`;
  }

  const diffDays = Math.round(diffHours / 24);
  return `expiring in ${diffDays} day${diffDays === 1 ? "" : "s"}`;
};

export interface CollaboratorPresenceIndicatorProps {
  readonly projectId?: string;
  readonly sceneId?: string;
  readonly pollIntervalMs?: number;
  readonly className?: string;
}

export const CollaboratorPresenceIndicator: React.FC<CollaboratorPresenceIndicatorProps> = ({
  projectId,
  sceneId,
  pollIntervalMs = DEFAULT_POLL_INTERVAL_MS,
  className,
}) => {
  const apiClient = React.useMemo(() => createSceneEditorApiClient(), []);
  const [projectState, setProjectState] = React.useState<ProjectResolutionState>(() =>
    projectId
      ? { status: "ready", projectId, projectName: null }
      : { status: "idle" },
  );
  const [presenceState, setPresenceState] = React.useState<PresenceState>({
    status: projectId ? "loading" : "idle",
    projectId: projectId ?? null,
    sessions: [],
    lastUpdatedAt: null,
  });

  React.useEffect(() => {
    if (projectId) {
      setProjectState({ status: "ready", projectId, projectName: null });
      setPresenceState((previous) => ({
        ...previous,
        status: previous.status === "ready" ? previous.status : "loading",
        projectId,
      }));
      return;
    }

    let isMounted = true;
    const controller = new AbortController();
    setProjectState({ status: "resolving" });

    const loadProjects = async () => {
      try {
        const response: AdventureProjectListResponse = await apiClient.listProjects({
          signal: controller.signal,
        });

        if (!isMounted) {
          return;
        }

        if (response.data.length === 0) {
          setProjectState({ status: "empty" });
          return;
        }

        const firstProject = response.data[0];
        setProjectState({
          status: "ready",
          projectId: firstProject.id,
          projectName: firstProject.name ?? firstProject.id,
        });
      } catch (error) {
        if (!isMounted) {
          return;
        }
        if (error instanceof Error && error.name === "AbortError") {
          return;
        }
        if (error instanceof SceneEditorApiError && error.status === 404) {
          setProjectState({
            status: "disabled",
            message: "Project management endpoints are not enabled for this API.",
          });
          return;
        }

        setProjectState({
          status: "error",
          message:
            error instanceof SceneEditorApiError
              ? error.message
              : "Unable to load projects. Please try again later.",
        });
      }
    };

    void loadProjects();

    return () => {
      isMounted = false;
      controller.abort();
    };
  }, [apiClient, projectId]);

  React.useEffect(() => {
    if (projectState.status === "ready") {
      let isMounted = true;
      let controller: AbortController | null = null;

      const refreshSessions = async () => {
        controller?.abort();
        controller = new AbortController();

        setPresenceState((previous) => ({
          ...previous,
          status: previous.status === "ready" ? previous.status : "loading",
          projectId: projectState.projectId,
        }));

        try {
          const response = await apiClient.listProjectCollaborationSessions(
            projectState.projectId,
            { signal: controller.signal },
          );

          if (!isMounted) {
            return;
          }

          setPresenceState({
            status: "ready",
            projectId: response.project_id,
            sessions: response.sessions,
            lastUpdatedAt: new Date().toISOString(),
          });
        } catch (error) {
          if (!isMounted) {
            return;
          }
          if (error instanceof Error && error.name === "AbortError") {
            return;
          }
          if (error instanceof SceneEditorApiError && error.status === 404) {
            setPresenceState({
              status: "disabled",
              projectId: null,
              sessions: [],
              lastUpdatedAt: null,
              error: "Collaboration metadata is not available for this project.",
            });
            return;
          }

          setPresenceState((previous) => ({
            status: "error",
            projectId: previous.projectId ?? projectState.projectId,
            sessions: previous.sessions,
            lastUpdatedAt: previous.lastUpdatedAt,
            error:
              error instanceof SceneEditorApiError
                ? error.message
                : "Unable to load collaboration activity. Please try again later.",
          }));
        }
      };

      void refreshSessions();
      const intervalId = window.setInterval(() => {
        void refreshSessions();
      }, Math.max(5000, pollIntervalMs));

      return () => {
        isMounted = false;
        controller?.abort();
        window.clearInterval(intervalId);
      };
    }

    if (projectState.status === "disabled") {
      setPresenceState({
        status: "disabled",
        projectId: null,
        sessions: [],
        lastUpdatedAt: null,
        error: projectState.message,
      });
      return;
    }

    if (projectState.status === "empty") {
      setPresenceState({
        status: "disabled",
        projectId: null,
        sessions: [],
        lastUpdatedAt: null,
        error: "No projects are available. Create a project to enable collaboration features.",
      });
      return;
    }

    if (projectState.status === "error") {
      setPresenceState({
        status: "error",
        projectId: null,
        sessions: [],
        lastUpdatedAt: null,
        error: projectState.message,
      });
      return;
    }

    if (projectState.status === "resolving") {
      setPresenceState((previous) => ({
        ...previous,
        status: previous.status === "ready" ? previous.status : "loading",
      }));
      return;
    }

    setPresenceState((previous) => ({
      ...previous,
      status: "idle",
      projectId: null,
    }));
  }, [apiClient, pollIntervalMs, projectState]);

  const projectLabel = React.useMemo(() => {
    if (projectState.status === "ready") {
      return projectState.projectName ?? projectState.projectId;
    }
    return null;
  }, [projectState]);

  let content: React.ReactNode;

  if (presenceState.status === "loading" || presenceState.status === "idle") {
    content = (
      <p className="text-sm text-slate-300">Loading collaborator activity…</p>
    );
  } else if (presenceState.status === "error") {
    content = (
      <div
        role="alert"
        className="rounded-md border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-sm text-rose-100"
      >
        {presenceState.error ?? "Unable to load collaboration activity."}
      </div>
    );
  } else if (presenceState.status === "disabled") {
    content = (
      <div className="rounded-md border border-slate-800/60 bg-slate-900/40 px-3 py-2 text-sm text-slate-300">
        {presenceState.error ?? "Collaboration metadata is not currently available."}
      </div>
    );
  } else if (presenceState.sessions.length === 0) {
    content = (
      <div className="rounded-md border border-slate-800/60 bg-slate-900/40 px-3 py-3 text-sm text-slate-300">
        No active collaborators are online right now. You’ll be the first to make
        changes to this scene.
      </div>
    );
  } else {
    content = (
      <div className="flex flex-col gap-4">
        <p className="text-sm text-slate-300">
          {presenceState.sessions.length} collaborator{presenceState.sessions.length === 1 ? "" : "s"}
          {" "}
          currently active{projectLabel ? ` on ${projectLabel}` : ""}.
        </p>
        <ul className="space-y-3">
          {presenceState.sessions.map((session) => {
            const name = session.display_name?.trim() || session.user_id;
            const initials = getInitials(name);
            const focusDescription = describeSceneFocus(session, sceneId ?? undefined);
            const expiresLabel = formatExpiry(session.expires_at);
            const isFocusedScene = Boolean(
              sceneId && session.scene_id && session.scene_id === sceneId,
            );

            return (
              <li
                key={session.session_id}
                className="flex items-start gap-3 rounded-lg border border-slate-800/60 bg-slate-900/40 p-3"
              >
                <span
                  className="flex h-10 w-10 flex-none items-center justify-center rounded-full bg-indigo-500/30 text-sm font-semibold text-indigo-100 ring-1 ring-inset ring-indigo-400/50"
                  aria-hidden
                >
                  {initials}
                </span>
                <div className="flex min-w-0 flex-1 flex-col gap-1 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-slate-100">{name}</span>
                    <Badge size="sm" variant={roleVariants[session.role]}>
                      {roleLabels[session.role]}
                    </Badge>
                    {session.scene_id ? (
                      <Badge
                        size="sm"
                        variant={isFocusedScene ? "success" : "neutral"}
                      >
                        {isFocusedScene ? "This scene" : session.scene_id}
                      </Badge>
                    ) : null}
                  </div>
                  <p className="text-xs text-slate-400">
                    {focusDescription}
                    {" • "}
                    Last heartbeat {formatRelativeTime(session.last_heartbeat)}
                    {expiresLabel ? ` • ${expiresLabel}` : ""}
                  </p>
                </div>
              </li>
            );
          })}
        </ul>
        {presenceState.lastUpdatedAt ? (
          <p className="text-xs text-slate-500">
            Refreshed {formatRelativeTime(presenceState.lastUpdatedAt)}.
          </p>
        ) : null}
      </div>
    );
  }

  return (
    <div className={classNames("flex flex-col gap-3", className)}>
      {projectLabel ? (
        <p className="text-xs uppercase tracking-wide text-slate-400">
          Tracking project activity for {projectLabel}
        </p>
      ) : null}
      {content}
    </div>
  );
};

export default CollaboratorPresenceIndicator;
