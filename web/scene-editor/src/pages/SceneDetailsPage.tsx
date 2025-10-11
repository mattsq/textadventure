import React from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  createSceneEditorApiClient,
  SceneEditorApiError,
  type ChoiceResource,
  type SceneResource,
  type ValidationIssue,
} from "../api";
import { EditorPanel } from "../components/layout";
import { Badge, Card } from "../components/display";
import { TextAreaField, TextField } from "../components/forms";
import {
  ChoiceListEditor,
  type ChoiceEditorFieldErrors,
  type ChoiceEditorItem,
} from "../components/scene-editor";
import { useSceneEditorStore } from "../state";

const formatTimestamp = (value: string): string => {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString();
};

const statusToneClasses: Record<"info" | "success" | "error", string> = {
  info: "border-sky-500/40 bg-sky-500/10 text-sky-100",
  success: "border-emerald-500/40 bg-emerald-500/10 text-emerald-100",
  error: "border-rose-500/40 bg-rose-500/10 text-rose-100",
};

const validationSeverityLabels: Record<ValidationIssue["severity"], string> = {
  warning: "Warning",
  error: "Error",
};

const validationSeverityVariants: Record<
  ValidationIssue["severity"],
  React.ComponentProps<typeof Badge>["variant"]
> = {
  warning: "warning",
  error: "danger",
};

const createChoiceKey = (): string => {
  const randomUuid =
    typeof globalThis.crypto !== "undefined" &&
    typeof globalThis.crypto.randomUUID === "function"
      ? globalThis.crypto.randomUUID()
      : null;

  if (randomUuid) {
    return randomUuid;
  }

  const randomSuffix = Math.random().toString(36).slice(2, 10);
  const timestamp = Date.now().toString(36);
  return `choice-${timestamp}-${randomSuffix}`;
};

const mapChoicesToDrafts = (
  choices: readonly ChoiceResource[],
): ChoiceEditorItem[] =>
  choices.map((choice) => ({
    key: createChoiceKey(),
    command: choice.command,
    description: choice.description,
  }));

interface FieldErrors {
  sceneId?: string;
  description?: string;
}

interface StatusNotice {
  readonly tone: "info" | "success" | "error";
  readonly message: string;
}

const buildStatusMessage = (
  message: string,
  tone: StatusNotice["tone"],
): StatusNotice => ({ message, tone });

const SceneDetailsPage: React.FC = () => {
  const params = useParams<{ sceneId: string }>();
  const navigate = useNavigate();
  const setNavigationLog = useSceneEditorStore((state) => state.setNavigationLog);

  const apiClient = React.useMemo(
    () =>
      createSceneEditorApiClient({
        baseUrl:
          typeof import.meta.env.VITE_SCENE_API_BASE_URL === "string" &&
          import.meta.env.VITE_SCENE_API_BASE_URL.trim() !== ""
            ? import.meta.env.VITE_SCENE_API_BASE_URL
            : undefined,
      }),
    [],
  );

  const routeSceneId = React.useMemo(
    () => (params.sceneId ? decodeURIComponent(params.sceneId) : null),
    [params.sceneId],
  );

  const [loadStatus, setLoadStatus] = React.useState<"idle" | "loading" | "success" | "error">("idle");
  const [loadError, setLoadError] = React.useState<string | null>(null);
  const [scene, setScene] = React.useState<SceneResource | null>(null);
  const [validationIssues, setValidationIssues] = React.useState<
    readonly ValidationIssue[]
  >([]);
  const [formState, setFormState] = React.useState({
    sceneId: "",
    description: "",
    choices: [] as ChoiceEditorItem[],
  });
  const [fieldErrors, setFieldErrors] = React.useState<FieldErrors>({});
  const [statusNotice, setStatusNotice] = React.useState<StatusNotice | null>(null);
  const [isSaving, setIsSaving] = React.useState(false);
  const [choiceErrors, setChoiceErrors] = React.useState<
    Record<string, ChoiceEditorFieldErrors>
  >({});

  React.useEffect(() => {
    if (!routeSceneId) {
      setLoadStatus("error");
      setLoadError("Scene identifier missing from the URL.");
      return;
    }

    const abortController = new AbortController();
    setLoadStatus("loading");
    setLoadError(null);
    setStatusNotice(null);

    void (async () => {
      try {
        const response = await apiClient.getScene(routeSceneId, {
          include_validation: true,
          signal: abortController.signal,
        });

        setScene(response.data);
        setFormState({
          sceneId: response.data.id,
          description: response.data.description,
          choices: mapChoicesToDrafts(response.data.choices),
        });
        setValidationIssues(response.validation?.issues ?? []);
        setFieldErrors({});
        setChoiceErrors({});
        setLoadStatus("success");
        setNavigationLog(
          `Loaded scene "${response.data.id}" for detailed editing.`,
        );
      } catch (error) {
        if (abortController.signal.aborted) {
          return;
        }

        const message =
          error instanceof SceneEditorApiError
            ? error.message
            : "Unable to load the scene. Please try again.";
        setLoadStatus("error");
        setLoadError(message);
        setStatusNotice(buildStatusMessage(message, "error"));
        setNavigationLog(`Failed to load scene "${routeSceneId}".`);
      }
    })();

    return () => {
      abortController.abort();
    };
  }, [apiClient, routeSceneId, setNavigationLog]);

  const handleFieldChange = <T extends keyof typeof formState>(
    field: T,
    value: (typeof formState)[T],
  ) => {
    setFormState((previous) => ({ ...previous, [field]: value }));
    setFieldErrors((previous) => ({ ...previous, [field]: undefined }));
    setStatusNotice(null);
  };

  const handleReset = () => {
    if (!scene) {
      return;
    }

    setFormState({
      sceneId: scene.id,
      description: scene.description,
      choices: mapChoicesToDrafts(scene.choices),
    });
    setFieldErrors({});
    setChoiceErrors({});
    setStatusNotice(buildStatusMessage("Reverted changes to the last saved state.", "info"));
    setNavigationLog(`Reverted edits for scene "${scene.id}".`);
  };

  const trimmedSceneId = formState.sceneId.trim();
  const trimmedDescription = formState.description.trim();
  const trimmedChoices = React.useMemo(
    () =>
      formState.choices.map((choice) => ({
        key: choice.key,
        command: choice.command.trim(),
        description: choice.description.trim(),
      })),
    [formState.choices],
  );
  const isDirty =
    scene !== null &&
    ((trimmedSceneId !== scene.id || trimmedDescription !== scene.description ||
      trimmedChoices.length !== scene.choices.length ||
      trimmedChoices.some((choice, index) => {
        const original = scene.choices[index];
        if (!original) {
          return true;
        }
        return (
          choice.command !== original.command.trim() ||
          choice.description !== original.description.trim()
        );
      })));

  const handleChoiceChange = (
    choiceKey: string,
    field: "command" | "description",
    value: string,
  ) => {
    setFormState((previous) => ({
      ...previous,
      choices: previous.choices.map((choice) =>
        choice.key === choiceKey ? { ...choice, [field]: value } : choice,
      ),
    }));

    setChoiceErrors((previous) => {
      const existing = previous[choiceKey];
      if (!existing) {
        return previous;
      }

      const updated: ChoiceEditorFieldErrors = { ...existing, [field]: undefined };
      if (!updated.command && !updated.description) {
        const { [choiceKey]: _removed, ...rest } = previous;
        return rest;
      }

      return { ...previous, [choiceKey]: updated };
    });

    setStatusNotice(null);
  };

  const handleAddChoice = () => {
    setFormState((previous) => ({
      ...previous,
      choices: [
        ...previous.choices,
        { key: createChoiceKey(), command: "", description: "" },
      ],
    }));
    setStatusNotice(null);
  };

  const handleRemoveChoice = (choiceKey: string) => {
    setFormState((previous) => ({
      ...previous,
      choices: previous.choices.filter((choice) => choice.key !== choiceKey),
    }));
    setChoiceErrors((previous) => {
      if (!previous[choiceKey]) {
        return previous;
      }

      const { [choiceKey]: _removed, ...rest } = previous;
      return rest;
    });
    setStatusNotice(null);
  };

  const handleMoveChoice = (choiceKey: string, direction: "up" | "down") => {
    setFormState((previous) => {
      const currentIndex = previous.choices.findIndex(
        (choice) => choice.key === choiceKey,
      );
      if (currentIndex === -1) {
        return previous;
      }

      const targetIndex =
        direction === "up" ? currentIndex - 1 : currentIndex + 1;
      if (targetIndex < 0 || targetIndex >= previous.choices.length) {
        return previous;
      }

      const nextChoices = [...previous.choices];
      const [moved] = nextChoices.splice(currentIndex, 1);
      nextChoices.splice(targetIndex, 0, moved);

      return { ...previous, choices: nextChoices };
    });
    setStatusNotice(null);
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!scene) {
      return;
    }

    const errors: FieldErrors = {};
    if (!trimmedSceneId) {
      errors.sceneId = "Scene ID is required.";
    } else if (!/^[a-z0-9-]+$/.test(trimmedSceneId)) {
      errors.sceneId = "Use lowercase letters, numbers, and dashes only.";
    }

    if (trimmedDescription.length === 0) {
      errors.description = "Provide a short description for collaborators.";
    }

    const nextChoiceErrors: Record<string, ChoiceEditorFieldErrors> = {};
    let hasChoiceErrors = false;
    const commandToKeys = new Map<string, string[]>();

    for (const choice of trimmedChoices) {
      const choiceIssues: ChoiceEditorFieldErrors = {};
      if (!choice.command) {
        choiceIssues.command = "Command is required.";
      } else {
        const keys = commandToKeys.get(choice.command) ?? [];
        keys.push(choice.key);
        commandToKeys.set(choice.command, keys);
      }

      if (!choice.description) {
        choiceIssues.description = "Description is required.";
      }

      if (choiceIssues.command || choiceIssues.description) {
        nextChoiceErrors[choice.key] = choiceIssues;
        hasChoiceErrors = true;
      }
    }

    for (const [, keys] of commandToKeys) {
      if (keys.length > 1) {
        hasChoiceErrors = true;
        for (const key of keys) {
          const existing = nextChoiceErrors[key] ?? {};
          nextChoiceErrors[key] = {
            ...existing,
            command: "Command must be unique per scene.",
          };
        }
      }
    }

    if (Object.keys(errors).length > 0 || hasChoiceErrors) {
      setFieldErrors(errors);
      setChoiceErrors(nextChoiceErrors);
      setStatusNotice(
        buildStatusMessage("Resolve the highlighted fields before saving.", "error"),
      );
      return;
    }

    setChoiceErrors({});

    if (!isDirty) {
      setStatusNotice(
        buildStatusMessage("No changes detected. Update a field before saving.", "info"),
      );
      return;
    }

    setIsSaving(true);
    setStatusNotice(buildStatusMessage("Saving changes…", "info"));

    try {
      const response = await apiClient.updateScene(scene.id, {
        id: trimmedSceneId,
        description: trimmedDescription,
        choices: trimmedChoices.map((choice) => ({
          command: choice.command,
          description: choice.description,
        })),
      });

      setScene(response.data);
      setFormState({
        sceneId: response.data.id,
        description: response.data.description,
        choices: mapChoicesToDrafts(response.data.choices),
      });
      setValidationIssues(response.validation?.issues ?? []);
      setFieldErrors({});
      setChoiceErrors({});
      setStatusNotice(buildStatusMessage("Scene saved successfully.", "success"));
      setNavigationLog(`Saved changes to scene "${response.data.id}".`);

      if (response.data.id !== scene.id) {
        navigate(`/scenes/${encodeURIComponent(response.data.id)}`, {
          replace: true,
        });
      }
    } catch (error) {
      const message =
        error instanceof SceneEditorApiError
          ? error.message
          : "Unable to save changes. Please try again.";
      setStatusNotice(buildStatusMessage(message, "error"));
    } finally {
      setIsSaving(false);
    }
  };

  const panelTitle = scene
    ? `Scene detail: ${scene.id}`
    : routeSceneId
      ? `Scene detail: ${routeSceneId}`
      : "Scene detail";

  return (
    <EditorPanel
      title={panelTitle}
      description="Edit the scene identifier, description, and branching choices before wiring in transitions."
    >
      {loadStatus === "loading" ? (
        <div className="rounded-lg border border-slate-800/60 bg-slate-900/40 px-4 py-3 text-sm text-slate-300">
          Loading scene details…
        </div>
      ) : null}

      {loadStatus === "error" && loadError ? (
        <div className="flex flex-col gap-4">
          <div
            className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-100"
            role="alert"
          >
            {loadError}
          </div>
          <button
            type="button"
            onClick={() => navigate("/scenes")}
            className="self-start rounded-md border border-slate-700 bg-slate-900/60 px-3 py-1.5 text-sm font-semibold text-slate-200 transition hover:border-indigo-400/50 hover:text-indigo-100"
          >
            Return to scene library
          </button>
        </div>
      ) : null}

      {loadStatus === "success" && scene ? (
        <div className="flex flex-col gap-6">
          <form className="grid gap-6 md:grid-cols-2" onSubmit={handleSubmit}>
            <TextField
              className="md:col-span-1"
              label="Scene ID"
              value={formState.sceneId}
              onChange={(event) => handleFieldChange("sceneId", event.target.value)}
              description="Unique identifier referenced by transitions, analytics, and tooling."
              placeholder="enter-scene-id"
              error={fieldErrors.sceneId}
              required
            />
            <TextAreaField
              className="md:col-span-2"
              label="Scene Description"
              value={formState.description}
              onChange={(event) =>
                handleFieldChange("description", event.target.value)
              }
              description="Summarise the scene so collaborators and future-you recognise it instantly."
              placeholder="Describe the scene's purpose, key beats, and atmosphere."
              rows={6}
              error={fieldErrors.description}
              required
            />
            <ChoiceListEditor
              className="md:col-span-2"
              choices={formState.choices}
              errors={choiceErrors}
              disabled={isSaving}
              onAddChoice={handleAddChoice}
              onRemoveChoice={handleRemoveChoice}
              onMoveChoice={handleMoveChoice}
              onChange={handleChoiceChange}
            />
            <div className="flex flex-col gap-3 md:col-span-2 md:flex-row md:items-center md:justify-between">
              <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400">
                <span>
                  Last updated {formatTimestamp(scene.updated_at)}
                </span>
                <span aria-hidden>•</span>
                <span>Created {formatTimestamp(scene.created_at)}</span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleReset}
                  className="rounded-md border border-slate-700/70 bg-slate-900/60 px-3 py-1.5 text-sm font-semibold text-slate-200 transition hover:border-indigo-400/60 hover:text-indigo-100 disabled:cursor-not-allowed disabled:border-slate-800 disabled:text-slate-500"
                  disabled={!isDirty || isSaving}
                >
                  Reset changes
                </button>
                <button
                  type="submit"
                  className="inline-flex items-center justify-center rounded-md border border-indigo-400/60 bg-indigo-500/30 px-4 py-2 text-sm font-semibold text-indigo-100 transition hover:bg-indigo-500/40 disabled:cursor-not-allowed disabled:border-slate-800 disabled:bg-slate-900/40 disabled:text-slate-500"
                  disabled={!isDirty || isSaving}
                >
                  {isSaving ? "Saving…" : "Save changes"}
                </button>
              </div>
            </div>
          </form>

          {statusNotice ? (
            <div
              className={`rounded-lg border px-4 py-3 text-sm transition ${statusToneClasses[statusNotice.tone]}`}
              role="status"
            >
              {statusNotice.message}
            </div>
          ) : null}

          <Card
            variant="subtle"
            title="Validation overview"
            description="API validation runs on save so you can keep an eye on warnings and blocking errors."
          >
            {validationIssues.length === 0 ? (
              <p className="text-slate-300">
                No validation issues reported for this scene. Add branching choices and transitions to see live analytics as you
                iterate.
              </p>
            ) : (
              <ul className="space-y-3">
                {validationIssues.map((issue) => (
                  <li key={`${issue.severity}-${issue.code}-${issue.path}`} className="flex flex-col gap-1">
                    <div className="flex items-center gap-2">
                      <Badge
                        variant={validationSeverityVariants[issue.severity]}
                        size="sm"
                      >
                        {validationSeverityLabels[issue.severity]}
                      </Badge>
                      <span className="font-semibold text-slate-100">{issue.code}</span>
                    </div>
                    <p className="text-slate-300">{issue.message}</p>
                    <span className="text-xs text-slate-500">Path: {issue.path}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      ) : null}
    </EditorPanel>
  );
};

export default SceneDetailsPage;
