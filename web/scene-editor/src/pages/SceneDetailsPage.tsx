import React from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import {
  createSceneEditorApiClient,
  SceneEditorApiError,
  type ChoiceResource,
  type TransitionResource,
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
  TransitionListEditor,
  type TransitionEditorFieldErrors,
  type TransitionEditorValues,
  type TransitionExtras,
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

const AUTO_SAVE_DEBOUNCE_MS = 2000;

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

const mapTransitionsToDrafts = (
  choices: readonly ChoiceEditorItem[],
  transitions: Readonly<Record<string, TransitionResource>>,
): {
  readonly drafts: Record<string, TransitionEditorValues>;
  readonly unmanaged: Record<string, TransitionResource>;
} => {
  const drafts: Record<string, TransitionEditorValues> = {};
  const assignedCommands = new Set<string>();

  for (const choice of choices) {
    const transition = transitions[choice.command];
    if (transition) {
      const { target, narration, ...extras } = transition;
      drafts[choice.key] = {
        target: target ?? null,
        narration: narration ?? "",
        extras: (extras as TransitionExtras) ?? ({} as TransitionExtras),
      };
      assignedCommands.add(choice.command);
    } else {
      drafts[choice.key] = {
        target: null,
        narration: "",
        extras: {} as TransitionExtras,
      };
    }
  }

  const unmanaged: Record<string, TransitionResource> = {};
  for (const [command, transition] of Object.entries(transitions)) {
    if (!assignedCommands.has(command)) {
      unmanaged[command] = transition;
    }
  }

  return { drafts, unmanaged };
};

const createEmptyTransition = (): TransitionEditorValues => ({
  target: null,
  narration: "",
  extras: {} as TransitionExtras,
});

const ORDER_INSENSITIVE_EXTRA_KEYS = new Set([
  "requires",
  "consumes",
  "records",
]);

const serializeTransition = (transition: TransitionResource): string => {
  const { target, narration, ...extras } = transition;
  const filteredExtras = Object.entries(extras).filter(
    ([, value]) => value !== undefined,
  );
  filteredExtras.sort(([a], [b]) => a.localeCompare(b));
  const normalisedExtras: Record<string, unknown> = {};
  for (const [key, value] of filteredExtras) {
    if (
      Array.isArray(value) &&
      ORDER_INSENSITIVE_EXTRA_KEYS.has(key) &&
      value.every((item) => typeof item === "string")
    ) {
      const sorted = [...value]
        .map((item) => (typeof item === "string" ? item.trim() : String(item)))
        .filter((item) => item.length > 0)
        .sort((a, b) => a.localeCompare(b));
      normalisedExtras[key] = sorted;
    } else {
      normalisedExtras[key] = value;
    }
  }

  return JSON.stringify({
    target: target ?? null,
    narration: (narration ?? "").trim(),
    extras: normalisedExtras,
  });
};

const normaliseStringList = (
  values?: readonly string[],
): readonly string[] | undefined => {
  if (!values) {
    return undefined;
  }

  const seen = new Set<string>();
  const result: string[] = [];

  for (const value of values) {
    const trimmed = value.trim();
    if (!trimmed) {
      continue;
    }
    const key = trimmed.toLowerCase();
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    result.push(trimmed);
  }

  return result.length > 0 ? result : undefined;
};

const areTransitionsEqual = (
  previous: Readonly<Record<string, TransitionResource>>,
  next: Readonly<Record<string, TransitionResource>>,
): boolean => {
  const previousKeys = Object.keys(previous).sort();
  const nextKeys = Object.keys(next).sort();

  if (previousKeys.length !== nextKeys.length) {
    return false;
  }

  for (let index = 0; index < previousKeys.length; index += 1) {
    if (previousKeys[index] !== nextKeys[index]) {
      return false;
    }
  }

  return previousKeys.every((key) => {
    const previousTransition = previous[key];
    const nextTransition = next[key];
    if (!previousTransition || !nextTransition) {
      return false;
    }

    return (
      serializeTransition(previousTransition) ===
      serializeTransition(nextTransition)
    );
  });
};

interface FieldErrors {
  sceneId?: string;
  description?: string;
}

interface StatusNotice {
  readonly tone: "info" | "success" | "error";
  readonly message: string;
}

interface ChoiceDraft {
  readonly key: string;
  readonly command: string;
  readonly description: string;
}

interface TransitionDraft {
  readonly key: string;
  readonly narration: string;
}

interface ValidationSnapshot {
  readonly fieldErrors: FieldErrors;
  readonly choiceErrors: Record<string, ChoiceEditorFieldErrors>;
  readonly transitionErrors: Record<string, TransitionEditorFieldErrors>;
  readonly hasErrors: boolean;
}

const areFieldErrorsEqual = (
  previous: FieldErrors,
  next: FieldErrors,
): boolean => {
  const previousKeys = Object.keys(previous) as (keyof FieldErrors)[];
  const nextKeys = Object.keys(next) as (keyof FieldErrors)[];

  if (previousKeys.length !== nextKeys.length) {
    return false;
  }

  return previousKeys.every(
    (key) => Object.prototype.hasOwnProperty.call(next, key) && previous[key] === next[key],
  );
};

const areChoiceErrorMapsEqual = (
  previous: Readonly<Record<string, ChoiceEditorFieldErrors>>,
  next: Readonly<Record<string, ChoiceEditorFieldErrors>>,
): boolean => {
  const previousKeys = Object.keys(previous);
  const nextKeys = Object.keys(next);

  if (previousKeys.length !== nextKeys.length) {
    return false;
  }

  return previousKeys.every((key) => {
    const previousErrors = previous[key];
    const nextErrors = next[key];
    if (!previousErrors && !nextErrors) {
      return true;
    }

    if (!previousErrors || !nextErrors) {
      return false;
    }

    const previousFields = Object.keys(previousErrors) as (keyof ChoiceEditorFieldErrors)[];
    const nextFields = Object.keys(nextErrors) as (keyof ChoiceEditorFieldErrors)[];

    if (previousFields.length !== nextFields.length) {
      return false;
    }

    return previousFields.every(
      (field) => Object.prototype.hasOwnProperty.call(nextErrors, field) && previousErrors[field] === nextErrors[field],
    );
  });
};

const areTransitionErrorMapsEqual = (
  previous: Readonly<Record<string, TransitionEditorFieldErrors>>,
  next: Readonly<Record<string, TransitionEditorFieldErrors>>,
): boolean => {
  const previousKeys = Object.keys(previous);
  const nextKeys = Object.keys(next);

  if (previousKeys.length !== nextKeys.length) {
    return false;
  }

  return previousKeys.every((key) => {
    const previousErrors = previous[key];
    const nextErrors = next[key];
    if (!previousErrors && !nextErrors) {
      return true;
    }

    if (!previousErrors || !nextErrors) {
      return false;
    }

    const previousFields = Object.keys(previousErrors) as (keyof TransitionEditorFieldErrors)[];
    const nextFields = Object.keys(nextErrors) as (keyof TransitionEditorFieldErrors)[];

    if (previousFields.length !== nextFields.length) {
      return false;
    }

    return previousFields.every(
      (field) => Object.prototype.hasOwnProperty.call(nextErrors, field) && previousErrors[field] === nextErrors[field],
    );
  });
};

const hasTransitionFieldError = (
  errors: TransitionEditorFieldErrors,
): boolean =>
  Boolean(errors.target || errors.narration || errors.requires || errors.consumes);

const buildValidationSnapshot = (
  sceneId: string,
  description: string,
  choices: readonly ChoiceDraft[],
  transitions: readonly TransitionDraft[],
): ValidationSnapshot => {
  const fieldErrors: FieldErrors = {};
  if (!sceneId) {
    fieldErrors.sceneId = "Scene ID is required.";
  } else if (!/^[a-z0-9-]+$/.test(sceneId)) {
    fieldErrors.sceneId = "Use lowercase letters, numbers, and dashes only.";
  }

  if (description.length === 0) {
    fieldErrors.description = "Provide a short description for collaborators.";
  }

  const choiceErrors: Record<string, ChoiceEditorFieldErrors> = {};
  const transitionErrors: Record<string, TransitionEditorFieldErrors> = {};
  let hasChoiceErrors = false;
  let hasTransitionErrors = false;
  const commandToKeys = new Map<string, string[]>();

  choices.forEach((choice, index) => {
    const nextChoiceErrors: ChoiceEditorFieldErrors = {};
    if (!choice.command) {
      nextChoiceErrors.command = "Command is required.";
    } else {
      const keys = commandToKeys.get(choice.command) ?? [];
      keys.push(choice.key);
      commandToKeys.set(choice.command, keys);
    }

    if (!choice.description) {
      nextChoiceErrors.description = "Description is required.";
    }

    if (nextChoiceErrors.command || nextChoiceErrors.description) {
      choiceErrors[choice.key] = nextChoiceErrors;
      hasChoiceErrors = true;
    }

    const transition = transitions[index];
    if (!transition) {
      return;
    }

    const nextTransitionErrors: TransitionEditorFieldErrors = {};
    if (!transition.narration) {
      nextTransitionErrors.narration = "Narration is required.";
    }

    if (nextTransitionErrors.narration) {
      transitionErrors[choice.key] = nextTransitionErrors;
      hasTransitionErrors = true;
    }
  });

  for (const [, keys] of commandToKeys) {
    if (keys.length > 1) {
      hasChoiceErrors = true;
      for (const key of keys) {
        const existing = choiceErrors[key] ?? {};
        choiceErrors[key] = {
          ...existing,
          command: "Command must be unique per scene.",
        };
      }
    }
  }

  return {
    fieldErrors,
    choiceErrors,
    transitionErrors,
    hasErrors:
      Object.keys(fieldErrors).length > 0 || hasChoiceErrors || hasTransitionErrors,
  };
};

const buildStatusMessage = (
  message: string,
  tone: StatusNotice["tone"],
): StatusNotice => ({ message, tone });

const SceneDetailsPage: React.FC = () => {
  const params = useParams<{ sceneId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
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

  const transitionFocusCommand = React.useMemo(() => {
    const searchParams = new URLSearchParams(location.search);
    const value = searchParams.get("transition");
    if (!value) {
      return null;
    }
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : null;
  }, [location.search]);

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
    transitions: {} as Record<string, TransitionEditorValues>,
  });
  const [fieldErrors, setFieldErrors] = React.useState<FieldErrors>({});
  const [statusNotice, setStatusNotice] = React.useState<StatusNotice | null>(null);
  const [isSaving, setIsSaving] = React.useState(false);
  const [choiceErrors, setChoiceErrors] = React.useState<
    Record<string, ChoiceEditorFieldErrors>
  >({});
  const [transitionErrors, setTransitionErrors] = React.useState<
    Record<string, TransitionEditorFieldErrors>
  >({});
  const [unmanagedTransitions, setUnmanagedTransitions] = React.useState<
    Readonly<Record<string, TransitionResource>>
  >({});
  const [targetSceneOptions, setTargetSceneOptions] = React.useState<readonly string[]>([]);
  const transitionItemRefs = React.useRef(new Map<string, HTMLLIElement>());
  const lastHighlightedChoiceKeyRef = React.useRef<string | null>(null);
  const getTransitionItemRef = React.useCallback(
    (choiceKey: string) => (element: HTMLLIElement | null) => {
      if (element) {
        transitionItemRefs.current.set(choiceKey, element);
      } else {
        transitionItemRefs.current.delete(choiceKey);
      }
    },
    [],
  );

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
        const choiceDrafts = mapChoicesToDrafts(response.data.choices);
        const { drafts, unmanaged } = mapTransitionsToDrafts(
          choiceDrafts,
          response.data.transitions,
        );
        setFormState({
          sceneId: response.data.id,
          description: response.data.description,
          choices: choiceDrafts,
          transitions: drafts,
        });
        setUnmanagedTransitions(unmanaged);
        setValidationIssues(response.validation?.issues ?? []);
        setFieldErrors({});
        setChoiceErrors({});
        setTransitionErrors({});
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

  React.useEffect(() => {
    const abortController = new AbortController();

    void (async () => {
      try {
        const response = await apiClient.listScenes({
          page_size: 200,
          signal: abortController.signal,
        });
        const sceneIds = Array.from(
          new Set(response.data.map((item) => item.id)),
        ).sort((a, b) => a.localeCompare(b));
        setTargetSceneOptions(sceneIds);
      } catch (error) {
        if (!abortController.signal.aborted) {
          setTargetSceneOptions([]);
        }
      }
    })();

    return () => {
      abortController.abort();
    };
  }, [apiClient]);

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

    const choiceDrafts = mapChoicesToDrafts(scene.choices);
    const { drafts, unmanaged } = mapTransitionsToDrafts(
      choiceDrafts,
      scene.transitions,
    );

    setFormState({
      sceneId: scene.id,
      description: scene.description,
      choices: choiceDrafts,
      transitions: drafts,
    });
    setUnmanagedTransitions(unmanaged);
    setFieldErrors({});
    setChoiceErrors({});
    setTransitionErrors({});
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

  const highlightedChoiceKey = React.useMemo(() => {
    if (!transitionFocusCommand) {
      return null;
    }

    const match = trimmedChoices.find(
      (choice) => choice.command === transitionFocusCommand,
    );
    return match?.key ?? null;
  }, [transitionFocusCommand, trimmedChoices]);

  interface TrimmedTransitionItem {
    readonly key: string;
    readonly command: string;
    readonly target: string | null;
    readonly narration: string;
    readonly extras: TransitionExtras;
  }

  const trimmedTransitions = React.useMemo<TrimmedTransitionItem[]>(() => {
    return formState.choices.map((choice, index) => {
      const trimmedChoice = trimmedChoices[index];
      const transitionState =
        formState.transitions[choice.key] ?? createEmptyTransition();
      const rawTarget = transitionState.target;
      const normalisedTarget =
        typeof rawTarget === "string"
          ? rawTarget.trim().length > 0
            ? rawTarget.trim()
            : null
          : rawTarget;

      return {
        key: choice.key,
        command: trimmedChoice.command,
        target: normalisedTarget,
        narration: transitionState.narration.trim(),
        extras: {
          ...(transitionState.extras ?? ({} as TransitionExtras)),
          requires: normaliseStringList(
            transitionState.extras?.requires,
          ),
          consumes: normaliseStringList(
            transitionState.extras?.consumes,
          ),
        } as TransitionExtras,
      };
    });
  }, [formState.choices, formState.transitions, trimmedChoices]);

  const availableTargetOptions = React.useMemo(() => {
    const unique = new Set(targetSceneOptions);
    if (trimmedSceneId) {
      unique.add(trimmedSceneId);
    }
    return Array.from(unique).sort((a, b) => a.localeCompare(b));
  }, [targetSceneOptions, trimmedSceneId]);

  const availableItemOptions = React.useMemo(() => {
    const items = new Set<string>();

    const addItem = (value?: string | null) => {
      if (typeof value !== "string") {
        return;
      }
      const trimmed = value.trim();
      if (!trimmed) {
        return;
      }
      items.add(trimmed);
    };

    const addItems = (values?: readonly string[]) => {
      if (!values) {
        return;
      }
      for (const value of values) {
        addItem(value);
      }
    };

    for (const transition of Object.values(formState.transitions)) {
      if (!transition) {
        continue;
      }
      const extras = transition.extras;
      if (!extras) {
        continue;
      }
      addItem((extras as TransitionExtras).item ?? null);
      addItems(extras.requires);
      addItems(extras.consumes);
    }

    for (const transition of Object.values(unmanagedTransitions)) {
      addItem(transition.item ?? null);
      addItems(transition.requires);
      addItems(transition.consumes);
    }

    return Array.from(items).sort((a, b) => a.localeCompare(b));
  }, [formState.transitions, unmanagedTransitions]);

  const validationSnapshot = React.useMemo(
    () =>
      buildValidationSnapshot(trimmedSceneId, trimmedDescription, trimmedChoices, trimmedTransitions),
    [trimmedChoices, trimmedDescription, trimmedSceneId, trimmedTransitions],
  );

  const hasBlockingValidationErrors = validationSnapshot.hasErrors;

  React.useEffect(() => {
    if (!highlightedChoiceKey) {
      lastHighlightedChoiceKeyRef.current = null;
      return;
    }

    const element = transitionItemRefs.current.get(highlightedChoiceKey);
    if (!element) {
      return;
    }
    if (lastHighlightedChoiceKeyRef.current === highlightedChoiceKey) {
      return;
    }

    const handle = window.requestAnimationFrame(() => {
      element.scrollIntoView({ behavior: "smooth", block: "center" });
    });
    lastHighlightedChoiceKeyRef.current = highlightedChoiceKey;

    return () => {
      window.cancelAnimationFrame(handle);
    };
  }, [highlightedChoiceKey]);

  React.useEffect(() => {
    setFieldErrors((previous) =>
      areFieldErrorsEqual(previous, validationSnapshot.fieldErrors)
        ? previous
        : validationSnapshot.fieldErrors,
    );
    setChoiceErrors((previous) =>
      areChoiceErrorMapsEqual(previous, validationSnapshot.choiceErrors)
        ? previous
        : validationSnapshot.choiceErrors,
    );
    setTransitionErrors((previous) =>
      areTransitionErrorMapsEqual(previous, validationSnapshot.transitionErrors)
        ? previous
        : validationSnapshot.transitionErrors,
    );
  }, [validationSnapshot]);

  const combinedTransitions = React.useMemo(
    () => {
      const map: Record<string, TransitionResource> = {
        ...unmanagedTransitions,
      };

      for (const item of trimmedTransitions) {
        if (!item.command) {
          continue;
        }

        map[item.command] = {
          ...item.extras,
          target: item.target,
          narration: item.narration,
        };
      }

      return map;
    },
    [trimmedTransitions, unmanagedTransitions],
  );

  const transitionsDirty =
    scene !== null
      ? !areTransitionsEqual(scene.transitions, combinedTransitions)
      : false;

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
      }) ||
      transitionsDirty));

  const performSave = React.useCallback(
    async (mode: "manual" | "auto") => {
      if (!scene) {
        return false;
      }

      if (validationSnapshot.hasErrors) {
        if (mode === "manual") {
          setFieldErrors(validationSnapshot.fieldErrors);
          setChoiceErrors(validationSnapshot.choiceErrors);
          setTransitionErrors(validationSnapshot.transitionErrors);
          setStatusNotice(
            buildStatusMessage(
              "Resolve the highlighted fields before saving.",
              "error",
            ),
          );
        }

        return false;
      }

      if (!isDirty) {
        if (mode === "manual") {
          setStatusNotice(
            buildStatusMessage(
              "No changes detected. Update a field before saving.",
              "info",
            ),
          );
        }

        return false;
      }

      setChoiceErrors({});
      setTransitionErrors({});
      setIsSaving(true);
      setStatusNotice(
        buildStatusMessage(
          mode === "auto" ? "Auto-saving changes…" : "Saving changes…",
          "info",
        ),
      );

      try {
        const transitionsPayload: Record<string, TransitionResource> = {
          ...unmanagedTransitions,
        };

        for (const item of trimmedTransitions) {
          if (!item.command) {
            continue;
          }

          transitionsPayload[item.command] = {
            ...item.extras,
            target: item.target,
            narration: item.narration,
          };
        }

        const response = await apiClient.updateScene(scene.id, {
          scene: {
            description: trimmedDescription,
            choices: trimmedChoices.map((choice) => ({
              command: choice.command,
              description: choice.description,
            })),
            transitions: transitionsPayload,
          },
        });

        setScene(response.data);
        const choiceDrafts = mapChoicesToDrafts(response.data.choices);
        const { drafts, unmanaged } = mapTransitionsToDrafts(
          choiceDrafts,
          response.data.transitions,
        );
        setFormState({
          sceneId: response.data.id,
          description: response.data.description,
          choices: choiceDrafts,
          transitions: drafts,
        });
        setUnmanagedTransitions(unmanaged);
        setValidationIssues(response.validation?.issues ?? []);
        setFieldErrors({});
        setChoiceErrors({});
        setTransitionErrors({});

        const successMessage =
          mode === "auto"
            ? `Auto-saved at ${new Date().toLocaleTimeString()}.`
            : "Scene saved successfully.";
        setStatusNotice(buildStatusMessage(successMessage, "success"));
        setNavigationLog(
          mode === "auto"
            ? `Auto-saved scene "${response.data.id}" after idle period.`
            : `Saved changes to scene "${response.data.id}".`,
        );

        if (response.data.id !== scene.id) {
          navigate(`/scenes/${encodeURIComponent(response.data.id)}`, {
            replace: true,
          });
        }

        return true;
      } catch (error) {
        const message =
          error instanceof SceneEditorApiError
            ? error.message
            : "Unable to save changes. Please try again.";
        setStatusNotice(buildStatusMessage(message, "error"));

        return false;
      } finally {
        setIsSaving(false);
      }
    },
    [
      apiClient,
      isDirty,
      navigate,
      scene,
      setChoiceErrors,
      setFieldErrors,
      setNavigationLog,
      setStatusNotice,
      setTransitionErrors,
      setUnmanagedTransitions,
      setValidationIssues,
      trimmedChoices,
      trimmedDescription,
      trimmedSceneId,
      trimmedTransitions,
      unmanagedTransitions,
      validationSnapshot,
    ],
  );

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
    const newChoiceKey = createChoiceKey();
    setFormState((previous) => ({
      ...previous,
      choices: [
        ...previous.choices,
        { key: newChoiceKey, command: "", description: "" },
      ],
      transitions: {
        ...previous.transitions,
        [newChoiceKey]: createEmptyTransition(),
      },
    }));
    setStatusNotice(null);
  };

  const handleRemoveChoice = (choiceKey: string) => {
    setFormState((previous) => {
      const { [choiceKey]: _removedTransition, ...restTransitions } =
        previous.transitions;
      return {
        ...previous,
        choices: previous.choices.filter((choice) => choice.key !== choiceKey),
        transitions: restTransitions,
      };
    });
    setChoiceErrors((previous) => {
      if (!previous[choiceKey]) {
        return previous;
      }

      const { [choiceKey]: _removed, ...rest } = previous;
      return rest;
    });
    setTransitionErrors((previous) => {
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

  const handleTransitionTargetChange = (choiceKey: string, value: string) => {
    setFormState((previous) => ({
      ...previous,
      transitions: {
        ...previous.transitions,
        [choiceKey]: {
          ...(previous.transitions[choiceKey] ?? createEmptyTransition()),
          target: value === "" ? null : value,
        },
      },
    }));

    setTransitionErrors((previous) => {
      const existing = previous[choiceKey];
      if (!existing) {
        return previous;
      }

      const updated: TransitionEditorFieldErrors = {
        ...existing,
        target: undefined,
      };

      if (!hasTransitionFieldError(updated)) {
        const { [choiceKey]: _removed, ...rest } = previous;
        return rest;
      }

      return { ...previous, [choiceKey]: updated };
    });

    setStatusNotice(null);
  };

  const handleTransitionNarrationChange = (
    choiceKey: string,
    value: string,
  ) => {
    setFormState((previous) => ({
      ...previous,
      transitions: {
        ...previous.transitions,
        [choiceKey]: {
          ...(previous.transitions[choiceKey] ?? createEmptyTransition()),
          narration: value,
        },
      },
    }));

    setTransitionErrors((previous) => {
      const existing = previous[choiceKey];
      if (!existing) {
        return previous;
      }

      const updated: TransitionEditorFieldErrors = {
        ...existing,
        narration: undefined,
      };

      if (!hasTransitionFieldError(updated)) {
        const { [choiceKey]: _removed, ...rest } = previous;
        return rest;
      }

      return { ...previous, [choiceKey]: updated };
    });

    setStatusNotice(null);
  };

  const handleTransitionRequiresChange = (
    choiceKey: string,
    values: readonly string[],
  ) => {
    const normalised = normaliseStringList(values);

    setFormState((previous) => {
      const previousTransition =
        previous.transitions[choiceKey] ?? createEmptyTransition();
      const previousExtras =
        previousTransition.extras ?? ({} as TransitionExtras);

      const nextExtras: TransitionExtras = {
        ...previousExtras,
        requires: normalised,
      };

      return {
        ...previous,
        transitions: {
          ...previous.transitions,
          [choiceKey]: {
            ...previousTransition,
            extras: nextExtras,
          },
        },
      };
    });

    setTransitionErrors((previous) => {
      const existing = previous[choiceKey];
      if (!existing?.requires) {
        return previous;
      }

      const updated: TransitionEditorFieldErrors = {
        ...existing,
        requires: undefined,
      };

      if (!hasTransitionFieldError(updated)) {
        const { [choiceKey]: _removed, ...rest } = previous;
        return rest;
      }

      return { ...previous, [choiceKey]: updated };
    });

    setStatusNotice(null);
  };

  const handleTransitionConsumesChange = (
    choiceKey: string,
    values: readonly string[],
  ) => {
    const normalised = normaliseStringList(values);

    setFormState((previous) => {
      const previousTransition =
        previous.transitions[choiceKey] ?? createEmptyTransition();
      const previousExtras =
        previousTransition.extras ?? ({} as TransitionExtras);

      const nextExtras: TransitionExtras = {
        ...previousExtras,
        consumes: normalised,
      };

      return {
        ...previous,
        transitions: {
          ...previous.transitions,
          [choiceKey]: {
            ...previousTransition,
            extras: nextExtras,
          },
        },
      };
    });

    setTransitionErrors((previous) => {
      const existing = previous[choiceKey];
      if (!existing?.consumes) {
        return previous;
      }

      const updated: TransitionEditorFieldErrors = {
        ...existing,
        consumes: undefined,
      };

      if (!hasTransitionFieldError(updated)) {
        const { [choiceKey]: _removed, ...rest } = previous;
        return rest;
      }

      return { ...previous, [choiceKey]: updated };
    });

    setStatusNotice(null);
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void performSave("manual");
  };

  React.useEffect(() => {
    if (
      !scene ||
      isSaving ||
      !isDirty ||
      validationSnapshot.hasErrors
    ) {
      return undefined;
    }

    const timeoutId = window.setTimeout(() => {
      void performSave("auto");
    }, AUTO_SAVE_DEBOUNCE_MS);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [
    isDirty,
    isSaving,
    performSave,
    scene,
    validationSnapshot.hasErrors,
  ]);

  const panelTitle = scene
    ? `Scene detail: ${scene.id}`
    : routeSceneId
      ? `Scene detail: ${routeSceneId}`
      : "Scene detail";

  return (
    <EditorPanel
      title={panelTitle}
      description="Edit the scene identifier, description, branching choices, and transition outcomes to shape the adventure flow."
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
            <TransitionListEditor
              className="md:col-span-2"
              choices={formState.choices}
              transitions={formState.transitions}
              errors={transitionErrors}
              targetOptions={availableTargetOptions}
              itemOptions={availableItemOptions}
              disabled={isSaving}
              onTargetChange={handleTransitionTargetChange}
              onNarrationChange={handleTransitionNarrationChange}
              onRequiresChange={handleTransitionRequiresChange}
              onConsumesChange={handleTransitionConsumesChange}
              highlightedChoiceKey={highlightedChoiceKey}
              getItemRef={getTransitionItemRef}
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
                <div className="flex flex-col items-stretch gap-2 md:items-end">
                  {hasBlockingValidationErrors ? (
                    <p className="text-xs text-rose-300 md:text-right">
                      Fix the highlighted fields to enable saving.
                    </p>
                  ) : null}
                  <button
                    type="submit"
                    className="inline-flex items-center justify-center rounded-md border border-indigo-400/60 bg-indigo-500/30 px-4 py-2 text-sm font-semibold text-indigo-100 transition hover:bg-indigo-500/40 disabled:cursor-not-allowed disabled:border-slate-800 disabled:bg-slate-900/40 disabled:text-slate-500"
                    disabled={!isDirty || isSaving || hasBlockingValidationErrors}
                  >
                    {isSaving ? "Saving…" : "Save changes"}
                  </button>
                </div>
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
