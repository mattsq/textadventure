import React from "react";
import {
  EditorHeader,
  EditorPanel,
  EditorShell,
  EditorSidebar,
  type EditorSidebarSection,
} from "./components/layout";
import { SelectField, TextAreaField, TextField } from "./components/forms";
import { Badge, Card, DataTable, type DataTableColumn } from "./components/display";

const onboardingSections: EditorSidebarSection[] = [
  {
    title: "Quick Start",
    content: (
      <ul className="space-y-2">
        <li className="flex items-center gap-2">
          <span className="inline-flex h-2 w-2 rounded-full bg-editor-accent" aria-hidden />
          Launch the Vite dev server.
        </li>
        <li className="flex items-center gap-2">
          <span className="inline-flex h-2 w-2 rounded-full bg-sky-400" aria-hidden />
          Explore placeholder routes to validate layout primitives.
        </li>
      </ul>
    ),
  },
  {
    title: "Upcoming Tasks",
    content: (
      <ul className="space-y-2 text-xs leading-relaxed text-slate-300">
        <li>Wire shared state management for editor screens.</li>
        <li>Implement the API client wrapper with optimistic updates.</li>
        <li>Design navigation for scene list and detail pages.</li>
      </ul>
    ),
  },
];

type ValidationState = "clean" | "warnings" | "errors";

interface SceneTableRow {
  readonly id: string;
  readonly title: string;
  readonly type: "Branch" | "Linear" | "Ending" | "Puzzle";
  readonly choices: number;
  readonly transitions: number;
  readonly validation: ValidationState;
  readonly lastUpdated: string;
}

const sceneTableColumns: DataTableColumn<SceneTableRow>[] = [
  {
    id: "scene",
    header: "Scene",
    render: (row) => (
      <div className="flex flex-col">
        <span className="font-semibold text-slate-50">{row.title}</span>
        <span className="text-xs text-slate-400">{row.id}</span>
      </div>
    ),
  },
  {
    id: "type",
    header: "Type",
    align: "center",
    render: (row) => (
      <Badge variant="info" size="sm">
        {row.type}
      </Badge>
    ),
  },
  {
    id: "choices",
    header: "Choices",
    align: "center",
    accessor: (row) => row.choices,
  },
  {
    id: "transitions",
    header: "Transitions",
    align: "center",
    accessor: (row) => row.transitions,
  },
  {
    id: "validation",
    header: "Validation",
    align: "center",
    render: (row) => (
      <Badge
        variant={
          row.validation === "clean"
            ? "success"
            : row.validation === "warnings"
            ? "warning"
            : "danger"
        }
        size="sm"
      >
        {row.validation === "clean"
          ? "Ready"
          : row.validation === "warnings"
          ? "Review"
          : "Needs Fix"}
      </Badge>
    ),
  },
  {
    id: "lastUpdated",
    header: "Last Updated",
    align: "right",
    accessor: (row) => row.lastUpdated,
  },
];

const sampleSceneRows: SceneTableRow[] = [
  {
    id: "mysterious-grove",
    title: "Mysterious Grove",
    type: "Branch",
    choices: 3,
    transitions: 4,
    validation: "clean",
    lastUpdated: "2 minutes ago",
  },
  {
    id: "shrouded-altar",
    title: "Shrouded Altar",
    type: "Puzzle",
    choices: 2,
    transitions: 3,
    validation: "warnings",
    lastUpdated: "12 minutes ago",
  },
  {
    id: "lunar-eclipse",
    title: "Lunar Eclipse",
    type: "Ending",
    choices: 1,
    transitions: 1,
    validation: "errors",
    lastUpdated: "27 minutes ago",
  },
];

export const App: React.FC = () => {
  const [sceneId, setSceneId] = React.useState("mysterious-grove");
  const [sceneType, setSceneType] = React.useState("branch");
  const [sceneSummary, setSceneSummary] = React.useState("A moonlit clearing reveals a hidden ritual site.");
  const [statusMessage, setStatusMessage] = React.useState<string | null>(null);

  const sceneIdError = sceneId.trim() ? undefined : "Scene ID is required to save a draft.";

  const handleFormSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (sceneIdError) {
      setStatusMessage(null);
      return;
    }
    setStatusMessage(`Draft saved for ${sceneId.trim()}.`);
  };

  React.useEffect(() => {
    setStatusMessage(null);
  }, [sceneId, sceneType, sceneSummary]);

  return (
    <EditorShell
      header={
        <EditorHeader
          badge="Priority 10 Roadmap"
          title="Scene Editor"
          subtitle={
            <>
              Welcome to the browser-based authoring environment for text adventures. The interface will
              evolve into a full-featured editor as subsequent milestones add data views, live previews,
              and collaborative tooling.
            </>
          }
          actions={<span className="text-xs text-slate-400">Prototype UI milestone</span>}
        />
      }
      sidebar={<EditorSidebar title="Editor Overview" sections={onboardingSections} footer="Layout components now live." />}
      footer="Tailwind CSS utility classes power the shared layout components."
    >
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
        <EditorPanel
          title="Getting Started"
          description={
            <>
              These layout primitives provide consistent styling for upcoming editor views. Compose them
              to create dashboards, forms, and navigation that match the design system without duplicating
              utility classes in every screen.
            </>
          }
        >
          <p>
            Use the <code className="rounded bg-slate-900 px-1 py-0.5 text-xs">EditorShell</code> to frame pages with optional
            sidebars and shared headers. Drop <code className="rounded bg-slate-900 px-1 py-0.5 text-xs">EditorPanel</code>
            components inside the shell for consistent content blocks, and use <code className="rounded bg-slate-900 px-1 py-0.5 text-xs">EditorSidebar</code>
            to populate navigation, summaries, or contextual helpers.
          </p>
          <p>
            Future tasks will introduce data fetching, routing, and interactive scene editing experiences that leverage these
            foundational components.
          </p>
        </EditorPanel>

        <EditorPanel
          title="Component Showcase"
          variant="subtle"
          description="Quick tips for extending the component set as new editor surfaces come online."
        >
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <Card
              compact
              title="Form primitives"
              description="Input components provide consistent states, helper text, and validation messaging."
              actions={<Badge size="sm">Stable</Badge>}
            >
              <p className="text-slate-300">
                Reuse <code>TextField</code>, <code>SelectField</code>, and <code>TextAreaField</code> for upcoming editor flows
                to minimise duplicated Tailwind classes.
              </p>
            </Card>
            <Card
              compact
              title="Layout shells"
              description="Compose panels, shells, and sidebars to build new views quickly."
              actions={<Badge size="sm">Stable</Badge>}
            >
              <p className="text-slate-300">
                Combine <code>EditorShell</code>, <code>EditorPanel</code>, and <code>EditorSidebar</code> to create dashboards
                for scenes, analytics, or collaborative tools.
              </p>
            </Card>
            <Card
              compact
              title="Display components"
              description="Cards, badges, and tables showcase scene metadata with consistent styling."
              actions={<Badge variant="info" size="sm">New</Badge>}
            >
              <p className="text-slate-300">
                Adopt the new <code>Card</code>, <code>Badge</code>, and <code>DataTable</code> primitives as building blocks for
                dashboards and validation summaries.
              </p>
            </Card>
            <Card
              compact
              title="Document patterns"
              description="Keep usage guidelines current as primitives evolve."
              actions={<Badge variant="warning" size="sm">Todo</Badge>}
            >
              <p className="text-slate-300">
                Update the design system docs with examples, variant guidance, and theming tokens as additional UI is added.
              </p>
            </Card>
          </div>
        </EditorPanel>

        <EditorPanel
          title="Form Component Demo"
          description="Base input components provide consistent styling, validation states, and helper text markup."
        >
          <form className="grid gap-6 md:grid-cols-2" onSubmit={handleFormSubmit}>
            <TextField
              className="md:col-span-1"
              label="Scene ID"
              value={sceneId}
              onChange={(event) => setSceneId(event.target.value)}
              description="Unique identifier used when referencing this scene in transitions and analytics."
              placeholder="enter-scene-id"
              error={sceneIdError}
              required
            />
            <SelectField
              className="md:col-span-1"
              label="Scene Type"
              value={sceneType}
              onChange={(event) => setSceneType(event.target.value)}
              description="Categorise scenes to drive editor filtering and analytics."
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
              onChange={(event) => setSceneSummary(event.target.value)}
              description="Provide a short synopsis to help collaborators identify the scene at a glance."
              placeholder="Describe the key beats players should expect when they reach this scene."
              rows={5}
            />
            <div className="flex flex-col gap-3 md:col-span-2 md:flex-row md:items-center md:justify-between">
              <span
                className={
                  statusMessage
                    ? "text-xs font-medium text-emerald-400"
                    : "text-xs text-slate-400"
                }
              >
                {statusMessage ?? "Validation happens live as values change. Submit to simulate a draft save."}
              </span>
              <button
                type="submit"
                className="inline-flex items-center justify-center rounded-lg border border-indigo-400/60 bg-indigo-500/30 px-4 py-2 text-sm font-semibold text-indigo-100 transition hover:bg-indigo-500/40 disabled:cursor-not-allowed disabled:border-slate-700 disabled:bg-slate-800/60 disabled:text-slate-500"
                disabled={Boolean(sceneIdError)}
              >
                Save Draft
              </button>
            </div>
          </form>
        </EditorPanel>

        <EditorPanel
          title="Data Display Components"
          description="Scene summaries, validation states, and statistics can be presented with shared primitives."
        >
          <div className="grid gap-4 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <DataTable
                columns={sceneTableColumns}
                data={sampleSceneRows}
                caption="Sample dataset highlighting validation coverage for recent scenes"
              />
            </div>
            <div className="flex flex-col gap-4">
              <Card
                title="Status breakdown"
                description="Use badges to provide quick validation state overviews."
                footer="Status summaries will align with analytics from the validation engine."
              >
                <ul className="space-y-2 text-sm">
                  <li className="flex items-center justify-between">
                    <span className="text-slate-300">Ready for publish</span>
                    <Badge variant="success" size="sm">
                      12 scenes
                    </Badge>
                  </li>
                  <li className="flex items-center justify-between">
                    <span className="text-slate-300">Needs review</span>
                    <Badge variant="warning" size="sm">
                      5 scenes
                    </Badge>
                  </li>
                  <li className="flex items-center justify-between">
                    <span className="text-slate-300">Blocked</span>
                    <Badge variant="danger" size="sm">
                      1 scene
                    </Badge>
                  </li>
                </ul>
              </Card>
              <Card
                title="Design tokens"
                description="Cards and tables inherit Tailwind theme tokens for consistent surfaces."
                variant="subtle"
              >
                <p className="text-slate-300">
                  Extend component variants by mapping new Tailwind utility combinations to semantic names. Theme updates can
                  then roll out across the editor from a single location.
                </p>
              </Card>
            </div>
          </div>
        </EditorPanel>
      </div>
    </EditorShell>
  );
};

export default App;
