import React from "react";
import {
  EditorHeader,
  EditorPanel,
  EditorShell,
  EditorSidebar,
  type EditorSidebarSection,
} from "./components/layout";

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

export const App: React.FC = () => {
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
          <ul className="grid gap-3 md:grid-cols-2">
            <li className="rounded-lg border border-slate-800/60 bg-slate-900/40 p-4 text-sm">
              <h3 className="text-sm font-semibold text-white">Add Form Elements</h3>
              <p className="mt-2 text-slate-300">
                Mirror the styling tokens used here when building inputs, selects, and validation messages.
              </p>
            </li>
            <li className="rounded-lg border border-slate-800/60 bg-slate-900/40 p-4 text-sm">
              <h3 className="text-sm font-semibold text-white">Compose Layouts</h3>
              <p className="mt-2 text-slate-300">
                Combine panels with the sidebar to create split views for scene lists and detail editors.
              </p>
            </li>
            <li className="rounded-lg border border-slate-800/60 bg-slate-900/40 p-4 text-sm">
              <h3 className="text-sm font-semibold text-white">Document Patterns</h3>
              <p className="mt-2 text-slate-300">
                Update the design system documentation as new primitives and tokens are added.
              </p>
            </li>
            <li className="rounded-lg border border-slate-800/60 bg-slate-900/40 p-4 text-sm">
              <h3 className="text-sm font-semibold text-white">Iterate Quickly</h3>
              <p className="mt-2 text-slate-300">
                Tailwind utilities keep prototypes fast while maintaining visual consistency.
              </p>
            </li>
          </ul>
        </EditorPanel>
      </div>
    </EditorShell>
  );
};

export default App;
