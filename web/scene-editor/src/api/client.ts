export interface ApiClientOptions {
  readonly baseUrl?: string;
  readonly fetchImpl?: typeof fetch;
}

export interface ApiErrorDetail {
  readonly path?: string;
  readonly message: string;
}

export interface ApiErrorPayload {
  readonly error: {
    readonly code: string;
    readonly message: string;
    readonly details?: readonly ApiErrorDetail[];
  };
}

export class SceneEditorApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: readonly ApiErrorDetail[];

  constructor(
    status: number,
    code: string,
    message: string,
    details: readonly ApiErrorDetail[] = [],
  ) {
    super(message);
    this.name = "SceneEditorApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export type ValidationSeverity = "valid" | "warnings" | "errors";

export interface SceneSummary {
  readonly id: string;
  readonly description: string;
  readonly choice_count: number;
  readonly transition_count: number;
  readonly has_terminal_transition: boolean;
  readonly validation_status: ValidationSeverity;
  readonly updated_at: string;
}

export type CollaboratorRole = "owner" | "editor" | "viewer";

export interface AdventureProjectResource {
  readonly id: string;
  readonly name: string;
  readonly description: string | null;
  readonly scene_count: number;
  readonly collaborator_count: number;
  readonly created_at: string;
  readonly updated_at: string;
  readonly version_id: string;
  readonly checksum: string;
}

export interface AdventureProjectListResponse {
  readonly data: readonly AdventureProjectResource[];
}

export interface PaginationMetadata {
  readonly page: number;
  readonly page_size: number;
  readonly total_items: number;
  readonly total_pages: number;
}

export interface ListScenesResponse {
  readonly data: readonly SceneSummary[];
  readonly pagination: PaginationMetadata;
}

export interface ListScenesParams {
  readonly search?: string;
  readonly updated_after?: string;
  readonly include_validation?: boolean;
  readonly page?: number;
  readonly page_size?: number;
  readonly signal?: AbortSignal;
}

export interface ChoiceResource {
  readonly command: string;
  readonly description: string;
}

export interface TransitionResource {
  readonly narration: string;
  readonly target: string | null;
  readonly item?: string | null;
  readonly requires?: readonly string[];
  readonly consumes?: readonly string[];
  readonly records?: readonly string[];
  readonly failure_narration?: string | null;
  readonly narration_overrides?: readonly NarrationOverrideResource[];
}

export interface NarrationOverrideResource {
  readonly narration: string;
  readonly requires_history_all?: readonly string[];
  readonly requires_history_any?: readonly string[];
  readonly forbids_history_any?: readonly string[];
  readonly requires_inventory_all?: readonly string[];
  readonly requires_inventory_any?: readonly string[];
  readonly forbids_inventory_any?: readonly string[];
  readonly records?: readonly string[];
}

export interface SceneResource {
  readonly id: string;
  readonly description: string;
  readonly choices: readonly ChoiceResource[];
  readonly transitions: Readonly<Record<string, TransitionResource>>;
  readonly created_at: string;
  readonly updated_at: string;
}

export interface SceneDefinitionPayload {
  readonly description: string;
  readonly choices: readonly ChoiceResource[];
  readonly transitions: Readonly<Record<string, TransitionResource>>;
}

export interface SceneCreateRequest {
  readonly id: string;
  readonly scene: SceneDefinitionPayload;
  readonly schema_version?: number;
  readonly expected_version_id?: string;
}

export interface SceneUpdateRequest {
  readonly scene: SceneDefinitionPayload;
  readonly schema_version?: number;
  readonly expected_version_id?: string;
}

export interface SceneVersionInfo {
  readonly generated_at: string;
  readonly version_id: string;
  readonly checksum: string;
}

export interface ValidationIssue {
  readonly severity: "error" | "warning";
  readonly code: string;
  readonly message: string;
  readonly path: string;
}

export interface SceneResourceResponse {
  readonly data: SceneResource;
  readonly validation?: {
    readonly issues: readonly ValidationIssue[];
  };
}

export interface SceneMutationResponse {
  readonly data: SceneResource;
  readonly validation?: {
    readonly issues: readonly ValidationIssue[];
  };
  readonly version: SceneVersionInfo;
}

export interface SceneReferenceResource {
  readonly scene_id: string;
  readonly command: string;
}

export interface SceneReferenceListResponse {
  readonly scene_id: string;
  readonly data: readonly SceneReferenceResource[];
}

export type SceneCommentLocationType = "transition_narration";

export interface SceneCommentLocation {
  readonly type: SceneCommentLocationType;
  readonly choice_command: string;
}

export interface SceneCommentResource {
  readonly id: string;
  readonly author_id: string | null;
  readonly author_display_name: string | null;
  readonly body: string;
  readonly created_at: string;
}

export interface SceneCommentThreadResource {
  readonly id: string;
  readonly scene_id: string;
  readonly status: "open" | "resolved";
  readonly created_at: string;
  readonly updated_at: string;
  readonly resolved_at: string | null;
  readonly resolved_by: string | null;
  readonly location: SceneCommentLocation;
  readonly comments: readonly SceneCommentResource[];
}

export interface SceneCommentThreadListResponse {
  readonly project_id: string;
  readonly scene_id: string;
  readonly threads: readonly SceneCommentThreadResource[];
}

export interface SceneCommentThreadCreateRequest {
  readonly location: SceneCommentLocation;
  readonly body: string;
  readonly author_id?: string | null;
  readonly author_display_name?: string | null;
}

export interface SceneCommentReplyRequest {
  readonly body: string;
  readonly author_id?: string | null;
  readonly author_display_name?: string | null;
}

export interface SceneCommentResolveRequest {
  readonly resolved: boolean;
}

export interface ListSceneCommentThreadsParams {
  readonly locationType?: SceneCommentLocationType;
  readonly choiceCommand?: string;
  readonly signal?: AbortSignal;
}

export interface SceneCommentMutationOptions extends RequestOptions {
  readonly actingUserId?: string;
}

export interface ProjectCollaborationSessionResource {
  readonly session_id: string;
  readonly user_id: string;
  readonly role: CollaboratorRole;
  readonly display_name: string | null;
  readonly scene_id: string | null;
  readonly started_at: string;
  readonly last_heartbeat: string;
  readonly expires_at: string;
}

export interface ProjectCollaborationSessionListResponse {
  readonly project_id: string;
  readonly sessions: readonly ProjectCollaborationSessionResource[];
}

export interface SceneGraphNodeResource {
  readonly id: string;
  readonly description: string;
  readonly choice_count: number;
  readonly transition_count: number;
  readonly has_terminal_transition: boolean;
  readonly validation_status: ValidationSeverity;
}

export interface SceneGraphEdgeResource {
  readonly id: string;
  readonly source: string;
  readonly command: string;
  readonly target: string | null;
  readonly narration: string;
  readonly is_terminal: boolean;
  readonly item?: string | null;
  readonly requires: readonly string[];
  readonly consumes: readonly string[];
  readonly records: readonly string[];
  readonly failure_narration?: string | null;
  readonly override_count: number;
}

export interface SceneGraphResponse {
  readonly generated_at: string;
  readonly start_scene: string;
  readonly nodes: readonly SceneGraphNodeResource[];
  readonly edges: readonly SceneGraphEdgeResource[];
}

export interface SceneGraphParams {
  readonly startScene?: string;
}

export interface ValidationSummaryResponse {
  readonly data: {
    readonly issues: readonly ValidationIssue[];
  };
}

export interface ImportScenesResponse {
  readonly data: SceneResourceResponse;
}

export interface RequestOptions {
  readonly signal?: AbortSignal;
}

const DEFAULT_HEADERS: Readonly<Record<string, string>> = {
  Accept: "application/json",
};

const ABSOLUTE_URL_PATTERN = /^[a-zA-Z][a-zA-Z\d+\-.]*:\/\//;

/**
 * Normalise a provided base URL so callers can supply either a full origin or a
 * relative path. When the value omits an API prefix, default to `/api`.
 */
const normaliseBaseUrl = (baseUrl?: string): string => {
  if (baseUrl === undefined) {
    return "/api";
  }

  const trimmed = baseUrl.trim();
  if (trimmed === "") {
    return "/api";
  }

  const withoutTrailingSlash = trimmed.replace(/\/+$/, "");
  if (withoutTrailingSlash === "") {
    return "/api";
  }

  if (ABSOLUTE_URL_PATTERN.test(withoutTrailingSlash)) {
    try {
      const url = new URL(withoutTrailingSlash);
      if (url.pathname === "" || url.pathname === "/") {
        url.pathname = "/api";
      }
      return url.toString().replace(/\/+$/, "");
    } catch {
      // Fall through to relative handling when the absolute URL cannot be parsed.
    }
  }

  if (!withoutTrailingSlash.startsWith("/")) {
    return `/${withoutTrailingSlash}`;
  }

  if (withoutTrailingSlash === "/") {
    return "/api";
  }

  return withoutTrailingSlash;
};

const toQueryString = (params: Record<string, unknown>): string => {
  const entries = Object.entries(params).filter(([, value]) =>
    value !== undefined && value !== null && value !== "",
  );

  if (entries.length === 0) {
    return "";
  }

  const searchParams = new URLSearchParams();
  for (const [key, value] of entries) {
    if (Array.isArray(value)) {
      for (const item of value) {
        searchParams.append(key, String(item));
      }
    } else {
      searchParams.set(key, String(value));
    }
  }

  const queryString = searchParams.toString();
  return queryString ? `?${queryString}` : "";
};

const resolveFetchImpl = (fetchImpl?: typeof fetch): typeof fetch => {
  const resolved = fetchImpl ?? globalThis.fetch;
  if (!resolved) {
    throw new Error("Fetch implementation is not available in this environment.");
  }

  return resolved.bind(globalThis);
};

export class SceneEditorApiClient {
  private readonly baseUrl: string;
  private readonly fetchImpl: typeof fetch;

  constructor(options: ApiClientOptions = {}) {
    this.baseUrl = normaliseBaseUrl(options.baseUrl);
    this.fetchImpl = resolveFetchImpl(options.fetchImpl);
  }

  private buildUrl(path: string, query: Record<string, unknown> = {}): string {
    const normalisedPath = path.startsWith("/") ? path : `/${path}`;
    return `${this.baseUrl}${normalisedPath}${toQueryString(query)}`;
  }

  private async request<TResponse>(
    path: string,
    init: RequestInit = {},
    query: Record<string, unknown> = {},
  ): Promise<TResponse> {
    const { signal, headers, ...rest } = init;
    const requestHeaders = {
      ...DEFAULT_HEADERS,
      ...(headers as Record<string, string> | undefined),
    };

    const response = await this.fetchImpl(this.buildUrl(path, query), {
      ...rest,
      headers: requestHeaders,
      signal,
    });

    const contentType = response.headers.get("content-type") ?? "";
    const isJson = contentType.includes("application/json");

    if (!response.ok) {
      let payload: ApiErrorPayload | undefined;
      if (isJson) {
        try {
          payload = (await response.json()) as ApiErrorPayload;
        } catch (error) {
          // ignore JSON parse errors and fall back to generic message
        }
      }

      const code = payload?.error.code ?? "unknown_error";
      const message =
        payload?.error.message ??
        `Request to ${path} failed with status ${response.status}`;

      throw new SceneEditorApiError(
        response.status,
        code,
        message,
        payload?.error.details ?? [],
      );
    }

    if (response.status === 204) {
      return undefined as TResponse;
    }

    if (!isJson) {
      throw new SceneEditorApiError(
        response.status,
        "unsupported_media_type",
        `Expected JSON response but received '${contentType || "unknown"}'.`,
      );
    }

    return (await response.json()) as TResponse;
  }

  async listScenes(params: ListScenesParams = {}): Promise<ListScenesResponse> {
    const { signal, ...query } = params;
    return this.request<ListScenesResponse>("/scenes", { signal }, query);
  }

  async getScene(
    sceneId: string,
    options: { include_validation?: boolean } & RequestOptions = {},
  ): Promise<SceneResourceResponse> {
    const { signal, include_validation } = options;
    return this.request<SceneResourceResponse>(
      `/scenes/${encodeURIComponent(sceneId)}`,
      { signal },
      { include_validation },
    );
  }

  async createScene(
    payload: SceneCreateRequest,
    options: RequestOptions = {},
  ): Promise<SceneMutationResponse> {
    return this.request<SceneMutationResponse>(
      "/scenes",
      {
        method: "POST",
        body: JSON.stringify(payload),
        headers: { "Content-Type": "application/json" },
        signal: options.signal,
      },
    );
  }

  async updateScene(
    sceneId: string,
    payload: SceneUpdateRequest,
    options: RequestOptions & { version?: string } = {},
  ): Promise<SceneMutationResponse> {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (options.version) {
      headers["If-Match"] = options.version;
    }

    return this.request<SceneMutationResponse>(
      `/scenes/${encodeURIComponent(sceneId)}`,
      {
        method: "PUT",
        body: JSON.stringify(payload),
        headers,
        signal: options.signal,
      },
    );
  }

  async deleteScene(
    sceneId: string,
    options: RequestOptions & { version?: string } = {},
  ): Promise<void> {
    const headers: Record<string, string> = {};
    if (options.version) {
      headers["If-Match"] = options.version;
    }

    await this.request<void>(
      `/scenes/${encodeURIComponent(sceneId)}`,
      {
        method: "DELETE",
        headers,
        signal: options.signal,
      },
    );
  }

  async listSceneReferences(
    sceneId: string,
    options: RequestOptions = {},
  ): Promise<SceneReferenceListResponse> {
    return this.request<SceneReferenceListResponse>(
      `/scenes/${encodeURIComponent(sceneId)}/references`,
      { signal: options.signal },
    );
  }

  async validateScenes(options: RequestOptions = {}): Promise<ValidationSummaryResponse> {
    return this.request<ValidationSummaryResponse>(
      "/scenes/validate",
      { signal: options.signal },
    );
  }

  async exportScenes(options: RequestOptions = {}): Promise<SceneResourceResponse> {
    return this.request<SceneResourceResponse>(
      "/scenes/export",
      { signal: options.signal },
    );
  }

  async importScenes(
    payload: SceneResource,
    options: RequestOptions = {},
  ): Promise<ImportScenesResponse> {
    return this.request<ImportScenesResponse>(
      "/scenes/import",
      {
        method: "POST",
        body: JSON.stringify(payload),
        headers: { "Content-Type": "application/json" },
        signal: options.signal,
      },
    );
  }

  async getSceneGraph(
    params: SceneGraphParams = {},
    options: RequestOptions = {},
  ): Promise<SceneGraphResponse> {
    return this.request<SceneGraphResponse>(
      "/scenes/graph",
      { signal: options.signal },
      { start_scene: params.startScene },
    );
  }

  async listProjects(
    options: RequestOptions = {},
  ): Promise<AdventureProjectListResponse> {
    return this.request<AdventureProjectListResponse>(
      "/projects",
      { signal: options.signal },
    );
  }

  async listProjectCollaborationSessions(
    projectId: string,
    options: RequestOptions = {},
  ): Promise<ProjectCollaborationSessionListResponse> {
    return this.request<ProjectCollaborationSessionListResponse>(
      `/projects/${encodeURIComponent(projectId)}/collaboration/sessions`,
      { signal: options.signal },
    );
  }

  async listSceneCommentThreads(
    projectId: string,
    sceneId: string,
    params: ListSceneCommentThreadsParams = {},
  ): Promise<SceneCommentThreadListResponse> {
    const { signal, locationType, choiceCommand } = params;
    return this.request<SceneCommentThreadListResponse>(
      `/projects/${encodeURIComponent(projectId)}/scenes/${encodeURIComponent(sceneId)}/comments`,
      { signal },
      {
        location_type: locationType,
        choice_command: choiceCommand,
      },
    );
  }

  async createSceneCommentThread(
    projectId: string,
    sceneId: string,
    payload: SceneCommentThreadCreateRequest,
    options: SceneCommentMutationOptions = {},
  ): Promise<SceneCommentThreadResource> {
    return this.request<SceneCommentThreadResource>(
      `/projects/${encodeURIComponent(projectId)}/scenes/${encodeURIComponent(sceneId)}/comments`,
      {
        method: "POST",
        body: JSON.stringify(payload),
        headers: { "Content-Type": "application/json" },
        signal: options.signal,
      },
      {
        acting_user_id: options.actingUserId,
      },
    );
  }

  async replyToSceneCommentThread(
    projectId: string,
    sceneId: string,
    threadId: string,
    payload: SceneCommentReplyRequest,
    options: SceneCommentMutationOptions = {},
  ): Promise<SceneCommentThreadResource> {
    return this.request<SceneCommentThreadResource>(
      `/projects/${encodeURIComponent(projectId)}/scenes/${encodeURIComponent(sceneId)}/comments/${encodeURIComponent(threadId)}/replies`,
      {
        method: "POST",
        body: JSON.stringify(payload),
        headers: { "Content-Type": "application/json" },
        signal: options.signal,
      },
      {
        acting_user_id: options.actingUserId,
      },
    );
  }

  async setSceneCommentThreadResolution(
    projectId: string,
    sceneId: string,
    threadId: string,
    payload: SceneCommentResolveRequest,
    options: SceneCommentMutationOptions = {},
  ): Promise<SceneCommentThreadResource> {
    return this.request<SceneCommentThreadResource>(
      `/projects/${encodeURIComponent(projectId)}/scenes/${encodeURIComponent(sceneId)}/comments/${encodeURIComponent(threadId)}/resolution`,
      {
        method: "POST",
        body: JSON.stringify(payload),
        headers: { "Content-Type": "application/json" },
        signal: options.signal,
      },
      {
        acting_user_id: options.actingUserId,
      },
    );
  }
}

export const createSceneEditorApiClient = (
  options?: ApiClientOptions,
): SceneEditorApiClient => new SceneEditorApiClient(options);
