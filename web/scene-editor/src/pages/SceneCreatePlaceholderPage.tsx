import React from "react";
import { EditorPanel } from "../components/layout";
import { Badge, Card } from "../components/display";
import { SelectField } from "../components/forms";
import { useSceneEditorStore } from "../state";

const classNames = (...values: Array<string | false | null | undefined>): string =>
  values.filter(Boolean).join(" ");

type TemplateOptionId = "empty" | "copy";

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

const defaultDraftId = "untitled-scene";

const SceneCreateWizardPage: React.FC = () => {
  const [selectedTemplate, setSelectedTemplate] = React.useState<TemplateOptionId | null>(null);
  const [selectedSourceSceneId, setSelectedSourceSceneId] = React.useState<string>("");
  const [stepComplete, setStepComplete] = React.useState<boolean>(false);

  const sceneTableRows = useSceneEditorStore((state) => state.sceneTableState.data ?? []);
  const setSceneId = useSceneEditorStore((state) => state.setSceneId);
  const setSceneSummary = useSceneEditorStore((state) => state.setSceneSummary);
  const setSceneType = useSceneEditorStore((state) => state.setSceneType);
  const setStatusMessage = useSceneEditorStore((state) => state.setStatusMessage);
  const setNavigationLog = useSceneEditorStore((state) => state.setNavigationLog);
  const prepareSceneDuplicate = useSceneEditorStore((state) => state.prepareSceneDuplicate);

  const handleSelectTemplate = (templateId: TemplateOptionId) => {
    setSelectedTemplate(templateId);
    setStepComplete(false);
    if (templateId === "copy") {
      setSceneType("branch");
    }
  };

  const handleReset = () => {
    setSelectedTemplate(null);
    setSelectedSourceSceneId("");
    setStepComplete(false);
    setStatusMessage(null);
    setNavigationLog("Template selection reset.");
  };

  const handleContinue = () => {
    if (selectedTemplate === "empty") {
      setSceneId(defaultDraftId);
      setSceneSummary("");
      setSceneType("branch");
      setStatusMessage(
        "Draft initialised from the blank template. Metadata configuration will unlock in the next milestone.",
      );
      setNavigationLog("Creating a new scene from scratch.");
      setStepComplete(true);
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
        `Duplicating "${source.id}". Further wizard steps will guide metadata and transition updates soon.`,
      );
      setNavigationLog(`Scene duplication wizard initialised from "${source.id}".`);
      setStepComplete(true);
    }
  };

  const isContinueDisabled =
    !selectedTemplate || (selectedTemplate === "copy" && !selectedSourceSceneId) || stepComplete;

  const activeTemplate = TEMPLATE_OPTIONS.find((option) => option.id === selectedTemplate);

  return (
    <EditorPanel
      title="Create a new scene"
      description="Select how you would like to begin your scene. Guided metadata and narration steps will follow in future updates."
      footer="This wizard currently focuses on template selection. Subsequent milestones will add metadata, choice drafting, and validation review steps."
      actions={<Badge variant="info" size="sm">Wizard alpha</Badge>}
    >
      <div className="flex flex-wrap items-center gap-2 text-xs uppercase tracking-wide text-slate-400">
        <Badge variant="neutral" size="sm">Step 1 of 3</Badge>
        <span>Pick a starting template to scaffold your scene.</span>
      </div>

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
            onClick={handleContinue}
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

      {stepComplete ? (
        <Card
          variant="transparent"
          className="border border-emerald-500/30 bg-emerald-500/5"
          icon={<span aria-hidden className="text-emerald-300">✓</span>}
          title="Template locked in"
          description="You're ready for the next stage of the wizard. Metadata, narration, and validation flows will unlock in an upcoming milestone."
        />
      ) : (
        <p className="text-xs text-slate-400">
          Once you confirm your template, the next step will walk through metadata capture before diving into narration and
          branching logic.
        </p>
      )}
    </EditorPanel>
  );
};

export { SceneCreateWizardPage as SceneCreatePlaceholderPage };
export default SceneCreateWizardPage;
