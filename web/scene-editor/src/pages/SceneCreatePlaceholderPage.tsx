import React from "react";
import { EditorPanel } from "../components/layout";
import { Badge, Card } from "../components/display";
import { SelectField, TextAreaField, TextField } from "../components/forms";
import { useSceneEditorStore } from "../state";

const classNames = (...values: Array<string | false | null | undefined>): string =>
  values.filter(Boolean).join(" ");

type TemplateOptionId = "empty" | "copy";

type WizardStep = 1 | 2;

type MetadataTouchedState = {
  readonly sceneId: boolean;
  readonly sceneSummary: boolean;
};

interface TemplateOption {
  readonly id: TemplateOptionId;
  readonly title: string;
  readonly description: string;
  readonly details: readonly string[];
  readonly badge?: {
    readonly label: string;
    readonly variant: React.ComponentProps<typeof Badge>["variant"];
  };
}

const TEMPLATE_OPTIONS: readonly TemplateOption[] = [
  {
    id: "empty",
    title: "Start from a blank canvas",
    description:
      "Create a brand-new scene with default metadata so you can draft narration and choices from scratch.",
    details: [
      "Pre-fills a draft scene identifier you can customise later.",
      "Sets up an empty choice list ready for authoring.",
      "Ideal when introducing entirely new branches to the adventure.",
    ],
    badge: { label: "Fresh start", variant: "success" },
  },
  {
    id: "copy",
    title: "Duplicate an existing scene",
    description:
      "Clone an existing scene to reuse its structure, narration, and transitions before making edits.",
    details: [
      "Copies narration, choices, and transitions into a new draft.",
      "Helps maintain consistent pacing and structure across related scenes.",
      "Great for iterating on variants of successful encounters.",
    ],
    badge: { label: "Reuse", variant: "info" },
  },
] as const;

const defaultDraftId = "untitled-scene";
const initialTouchedState: MetadataTouchedState = { sceneId: false, sceneSummary: false };
const slugPattern = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

const validateSceneId = (value: string): string | undefined => {
  const trimmed = value.trim();
  if (!trimmed) {
    return "Scene ID is required.";
  }
  if (!slugPattern.test(trimmed)) {
    return "Use lowercase letters, numbers, and dashes to create a stable ID.";
  }
  if (trimmed.length < 3) {
    return "Scene IDs should be at least three characters long.";
  }
  return undefined;
};

const validateSceneSummary = (value: string): string | undefined => {
  const trimmed = value.trim();
  if (!trimmed) {
    return "Add a short synopsis so collaborators recognise the scene.";
  }
  if (trimmed.length < 12) {
    return "Write at least a couple of sentences describing the encounter.";
  }
  return undefined;
};

interface TemplateOptionCardProps {
  readonly option: TemplateOption;
  readonly isSelected: boolean;
  readonly onSelect: () => void;
}

const TemplateOptionCard: React.FC<TemplateOptionCardProps> = ({
  option,
  isSelected,
  onSelect,
}) => (
  <button
    type="button"
    onClick={onSelect}
    className={classNames(
      "flex w-full flex-col gap-4 rounded-xl border p-5 text-left shadow-lg transition focus:outline-none focus:ring-2", // layout
      "focus:ring-indigo-400/60 focus:ring-offset-2 focus:ring-offset-slate-950", // focus styling
      isSelected
        ? "border-indigo-400/80 bg-indigo-500/10"
        : "border-slate-800/70 bg-slate-900/60 hover:border-indigo-400/60 hover:bg-slate-900/80",
    )}
  >
    <div className="flex items-start justify-between gap-3">
      <div className="flex flex-col gap-2">
        <span className="text-base font-semibold text-slate-50">{option.title}</span>
        <span className="text-sm text-slate-300">{option.description}</span>
      </div>
      <span
        className={classNames(
          "inline-flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full border", // base indicator
          isSelected
            ? "border-indigo-400 bg-indigo-500/40"
            : "border-slate-600 bg-slate-900",
        )}
        aria-hidden
      >
        <span className="h-2 w-2 rounded-full bg-indigo-200/90" hidden={!isSelected} />
      </span>
    </div>
    <ul className="space-y-1 text-xs text-slate-400">
      {option.details.map((detail) => (
        <li key={detail} className="flex items-start gap-2">
          <span className="mt-1 inline-flex h-1.5 w-1.5 flex-shrink-0 rounded-full bg-indigo-400/80" aria-hidden />
          <span>{detail}</span>
        </li>
      ))}
    </ul>
    {option.badge ? (
      <Badge variant={option.badge.variant} size="sm" className="self-start">
        {option.badge.label}
      </Badge>
    ) : null}
  </button>
);

const SceneCreateWizardPage: React.FC = () => {
  const [selectedTemplate, setSelectedTemplate] = React.useState<TemplateOptionId | null>(null);
  const [selectedSourceSceneId, setSelectedSourceSceneId] = React.useState<string>("");
  const [currentStep, setCurrentStep] = React.useState<WizardStep>(1);
  const [metadataTouched, setMetadataTouched] = React.useState<MetadataTouchedState>(initialTouchedState);
  const [metadataSaved, setMetadataSaved] = React.useState<boolean>(false);

  const sceneTableRows = useSceneEditorStore((state) => state.sceneTableState.data ?? []);
  const sceneId = useSceneEditorStore((state) => state.sceneId);
  const sceneSummary = useSceneEditorStore((state) => state.sceneSummary);
  const sceneType = useSceneEditorStore((state) => state.sceneType);
  const statusMessage = useSceneEditorStore((state) => state.statusMessage);
  const setSceneId = useSceneEditorStore((state) => state.setSceneId);
  const setSceneSummary = useSceneEditorStore((state) => state.setSceneSummary);
  const setSceneType = useSceneEditorStore((state) => state.setSceneType);
  const setStatusMessage = useSceneEditorStore((state) => state.setStatusMessage);
  const setNavigationLog = useSceneEditorStore((state) => state.setNavigationLog);
  const prepareSceneDuplicate = useSceneEditorStore((state) => state.prepareSceneDuplicate);

  const handleSelectTemplate = (templateId: TemplateOptionId) => {
    setSelectedTemplate(templateId);
    setMetadataTouched(initialTouchedState);
    setMetadataSaved(false);
    if (currentStep !== 1) {
      setCurrentStep(1);
    }
    if (templateId === "copy") {
      setSceneType("branch");
    }
  };

  const handleReset = () => {
    setSelectedTemplate(null);
    setSelectedSourceSceneId("");
    setCurrentStep(1);
    setMetadataTouched(initialTouchedState);
    setMetadataSaved(false);
    setSceneId(defaultDraftId);
    setSceneSummary("");
    setSceneType("branch");
    setStatusMessage(null);
    setNavigationLog("Template selection reset.");
  };

  const handleContinueFromTemplate = () => {
    if (selectedTemplate === "empty") {
      setSceneId(defaultDraftId);
      setSceneSummary("");
      setSceneType("branch");
      setStatusMessage(
        "Draft initialised from the blank template. Next, confirm the metadata so future steps can focus on narration and choices.",
      );
      setNavigationLog("Creating a new scene from scratch.");
      setCurrentStep(2);
      setMetadataTouched(initialTouchedState);
      setMetadataSaved(false);
      return;
    }

    if (selectedTemplate === "copy" && selectedSourceSceneId) {
      const source = sceneTableRows.find((row) => row.id === selectedSourceSceneId);
      if (!source) {
        setStatusMessage("Unable to locate the selected scene. Please refresh the library and try again.");
        return;
      }
      prepareSceneDuplicate(source);
      setStatusMessage(
        `Duplicating "${source.id}". Review the metadata before the wizard moves on to narration and branching logic.`,
      );
      setNavigationLog(`Scene duplication wizard initialised from "${source.id}".`);
      setCurrentStep(2);
      setMetadataTouched(initialTouchedState);
      setMetadataSaved(false);
    }
  };

  const handleChangeSceneId = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSceneId(event.target.value);
    setMetadataSaved(false);
  };

  const handleChangeSceneSummary = (
    event: React.ChangeEvent<HTMLTextAreaElement>,
  ) => {
    setSceneSummary(event.target.value);
    setMetadataSaved(false);
  };

  const handleChangeSceneType = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setSceneType(event.target.value);
    setMetadataSaved(false);
  };

  const handleMetadataBlur = (field: keyof MetadataTouchedState) => () => {
    setMetadataTouched((previous) => ({ ...previous, [field]: true }));
  };

  const handleBackToTemplates = () => {
    setCurrentStep(1);
    setMetadataTouched(initialTouchedState);
    setMetadataSaved(false);
    setStatusMessage(null);
    setNavigationLog("Returned to template selection to adjust the starting point.");
  };

  const handleMetadataConfirm = () => {
    setMetadataTouched({ sceneId: true, sceneSummary: true });
    const sceneIdValidation = validateSceneId(sceneId);
    const sceneSummaryValidation = validateSceneSummary(sceneSummary);

    if (sceneIdValidation || sceneSummaryValidation) {
      setStatusMessage("Resolve the highlighted metadata fields before continuing.");
      setMetadataSaved(false);
      return;
    }

    const trimmedId = sceneId.trim();
    setStatusMessage(
      `Metadata captured for ${trimmedId}. Choice drafting will unlock in the next milestone once this step is stable.`,
    );
    setNavigationLog(`Metadata configured for "${trimmedId}".`);
    setMetadataSaved(true);
  };

  const sceneIdValidation = validateSceneId(sceneId);
  const sceneSummaryValidation = validateSceneSummary(sceneSummary);
  const sceneIdError = metadataTouched.sceneId ? sceneIdValidation : undefined;
  const sceneSummaryError = metadataTouched.sceneSummary ? sceneSummaryValidation : undefined;

  const isTemplateStep = currentStep === 1;
  const isMetadataStep = currentStep === 2;

  const isContinueDisabled =
    !selectedTemplate || (selectedTemplate === "copy" && !selectedSourceSceneId);

  const activeTemplate = TEMPLATE_OPTIONS.find((option) => option.id === selectedTemplate);

  const stepBadgeLabel = isTemplateStep ? "Step 1 of 3" : "Step 2 of 3";
  const stepDescription = isTemplateStep
    ? "Pick a starting template to scaffold your scene."
    : "Capture the essentials so collaborators understand the scene at a glance.";

  const metadataStatusClassName = metadataSaved
    ? "text-xs font-semibold text-emerald-400"
    : statusMessage
    ? "text-xs font-semibold text-indigo-200"
    : "text-xs text-slate-400";

  const metadataStatusText = metadataSaved
    ? `Metadata captured for ${sceneId.trim() || "your scene"}. Branching tools will unlock soon.`
    : statusMessage ??
      "Fill out these basics so future wizard steps can focus on narration, choices, and validation.";

  return (
    <EditorPanel
      title="Create a new scene"
      description={
        isTemplateStep
          ? "Select how you would like to begin your scene. Guided metadata and narration steps will follow in future updates."
          : "Confirm the fundamentals so upcoming wizard stages can concentrate on narration, branching, and validation insights."
      }
      footer={
        isTemplateStep
          ? "This wizard currently focuses on template selection. Subsequent milestones will add metadata, choice drafting, and validation review steps."
          : "Next milestones will unlock branching tools, narration helpers, and validation previews once metadata capture is reliable."
      }
      actions={<Badge variant="info" size="sm">Wizard alpha</Badge>}
    >
      <div className="flex flex-wrap items-center gap-2 text-xs uppercase tracking-wide text-slate-400">
        <Badge variant="neutral" size="sm">{stepBadgeLabel}</Badge>
        <span>{stepDescription}</span>
      </div>

      {isTemplateStep ? (
        <>
          <div className="grid gap-4 md:grid-cols-2">
            {TEMPLATE_OPTIONS.map((option) => (
              <TemplateOptionCard
                key={option.id}
                option={option}
                isSelected={option.id === selectedTemplate}
                onSelect={() => handleSelectTemplate(option.id)}
              />
            ))}
          </div>

          {selectedTemplate === "copy" ? (
            <Card
              variant="subtle"
              title="Choose a source scene"
              description="The selected scene will be cloned into a new draft so you can edit it without affecting the original."
            >
              <SelectField
                label="Scene to duplicate"
                value={selectedSourceSceneId}
                onChange={(event) => setSelectedSourceSceneId(event.target.value)}
                description="Scene metadata is pulled from the library. Additional filters will arrive in a later iteration."
                required
              >
                <option value="" disabled>
                  Select a scene…
                </option>
                {sceneTableRows.map((scene) => (
                  <option key={scene.id} value={scene.id}>
                    {scene.id} — {scene.description}
                  </option>
                ))}
              </SelectField>
              <p className="text-xs text-slate-400">
                Need a different reference point? Return to the library to explore validation statuses and summaries before
                duplicating.
              </p>
            </Card>
          ) : null}

          <div className="flex flex-col gap-3 rounded-lg border border-slate-800/80 bg-slate-900/40 p-4 text-xs text-slate-300 md:flex-row md:items-center md:justify-between">
            <div className="flex flex-col gap-1">
              {activeTemplate ? (
                <>
                  <span className="font-semibold text-slate-100">{activeTemplate.title}</span>
                  <span>{activeTemplate.description}</span>
                </>
              ) : (
                <span>Select a template to preview its benefits.</span>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={handleReset}
                className="rounded-lg border border-slate-700/80 px-4 py-2 text-xs font-semibold text-slate-200 transition hover:border-indigo-400/60 hover:text-indigo-100"
              >
                Reset selection
              </button>
              <button
                type="button"
                onClick={handleContinueFromTemplate}
                disabled={isContinueDisabled}
                className={classNames(
                  "rounded-lg px-4 py-2 text-xs font-semibold transition focus:outline-none focus:ring-2 focus:ring-indigo-400/60 focus:ring-offset-2 focus:ring-offset-slate-950", // base
                  isContinueDisabled
                    ? "cursor-not-allowed border border-slate-800/70 bg-slate-800/30 text-slate-500"
                    : "border border-indigo-400/80 bg-indigo-500/30 text-indigo-50 hover:bg-indigo-500/40",
                )}
              >
                Continue to metadata
              </button>
            </div>
          </div>
        </>
      ) : null}

      {isMetadataStep ? (
        <>
          <Card
            variant="subtle"
            title="Metadata checkpoint"
            description="Lock in the essentials before drafting narration and branching logic."
            actions={
              <button
                type="button"
                onClick={handleBackToTemplates}
                className="rounded-lg border border-slate-700/80 px-3 py-1.5 text-xs font-semibold text-slate-200 transition hover:border-indigo-400/60 hover:text-indigo-100"
              >
                Change template
              </button>
            }
          >
            <ul className="space-y-2 text-xs text-slate-300">
              <li>
                Keep scene IDs stable and descriptive so transitions remain easy to follow in analytics and validation reports.
              </li>
              <li>
                Use the summary to highlight the narrative beat or purpose of the scene for collaborators.
              </li>
              <li>
                Scene types help filter large adventures and influence upcoming editor dashboards.
              </li>
            </ul>
          </Card>

          <form
            className="grid gap-5 md:grid-cols-2"
            onSubmit={(event) => {
              event.preventDefault();
              handleMetadataConfirm();
            }}
          >
            <TextField
              className="md:col-span-1"
              label="Scene ID"
              value={sceneId}
              onChange={handleChangeSceneId}
              onBlur={handleMetadataBlur("sceneId")}
              description="Use lowercase slugs so transitions can reference this scene reliably."
              placeholder="enter-scene-id"
              error={sceneIdError}
              required
            />
            <SelectField
              className="md:col-span-1"
              label="Scene Type"
              value={sceneType}
              onChange={handleChangeSceneType}
              description="Categorise scenes to power filtering, analytics, and future automation."
            >
              <option value="branch">Branching encounter</option>
              <option value="linear">Linear narration</option>
              <option value="terminal">Ending</option>
              <option value="puzzle">Puzzle / gated progress</option>
            </SelectField>
            <TextAreaField
              className="md:col-span-2"
              label="Scene Summary"
              value={sceneSummary}
              onChange={handleChangeSceneSummary}
              onBlur={handleMetadataBlur("sceneSummary")}
              description="Provide a synopsis so collaborators understand how this scene fits into the adventure."
              placeholder="Describe the key beats players should expect when they reach this scene."
              rows={5}
              error={sceneSummaryError}
            />
            <div className="flex flex-col gap-3 md:col-span-2 md:flex-row md:items-center md:justify-between">
              <span className={metadataStatusClassName}>{metadataStatusText}</span>
              <button
                type="submit"
                className={classNames(
                  "inline-flex items-center justify-center rounded-lg border px-4 py-2 text-xs font-semibold transition focus:outline-none focus:ring-2 focus:ring-indigo-400/60 focus:ring-offset-2 focus:ring-offset-slate-950",
                  metadataSaved
                    ? "cursor-not-allowed border-emerald-500/40 bg-emerald-500/10 text-emerald-200"
                    : "border border-indigo-400/80 bg-indigo-500/30 text-indigo-50 hover:bg-indigo-500/40",
                )}
                disabled={metadataSaved}
              >
                Save metadata
              </button>
            </div>
          </form>

          {metadataSaved ? (
            <Card
              variant="transparent"
              className="border border-emerald-500/30 bg-emerald-500/5"
              icon={<span aria-hidden className="text-emerald-300">✓</span>}
              title="Metadata locked in"
              description="You're ready for the next stage of the wizard. Branching, narration, and validation helpers will unlock soon."
            />
          ) : (
            <p className="text-xs text-slate-400">
              Once metadata is saved, the wizard will guide you through drafting choices, transitions, and validation checks in
              an upcoming milestone.
            </p>
          )}
        </>
      ) : null}
    </EditorPanel>
  );
};

export { SceneCreateWizardPage as SceneCreatePlaceholderPage };
export default SceneCreateWizardPage;
