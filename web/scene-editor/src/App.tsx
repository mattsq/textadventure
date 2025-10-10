import React from "react";

export const App: React.FC = () => {
  return (
    <div className="flex min-h-screen flex-col bg-editor-surface">
      <header className="border-b border-slate-800 bg-gradient-to-br from-editor-panel to-slate-900 px-6 py-8 shadow-lg">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-3 text-left">
          <span className="inline-flex w-fit items-center gap-2 rounded-full bg-editor-accent/10 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-editor-accent">
            Priority 10 Roadmap
          </span>
          <h1 className="text-3xl font-semibold text-white md:text-4xl">Scene Editor</h1>
          <p className="max-w-3xl text-sm text-slate-300 md:text-base">
            Welcome to the browser-based authoring environment for text adventures. The interface will
            evolve into a full-featured editor as subsequent milestones add data views, live previews,
            and collaborative tooling.
          </p>
        </div>
      </header>
      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-6 py-10">
        <section className="grid gap-4 rounded-xl border border-slate-800 bg-editor-panel/70 p-6 shadow-xl shadow-slate-950/40 backdrop-blur">
          <h2 className="text-xl font-semibold text-white md:text-2xl">Getting Started</h2>
          <p className="text-sm leading-relaxed text-slate-300 md:text-base">
            This placeholder confirms the React + TypeScript stack now ships with Tailwind CSS for
            rapid prototyping. Future tasks will replace this content with the actual editor experience,
            reusing the utility-first styling to build responsive layouts and interactive panels.
          </p>
          <div className="grid gap-2 rounded-lg border border-slate-800 bg-slate-900/60 p-4 md:grid-cols-2">
            <div>
              <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Developer Workflow</h3>
              <ul className="mt-2 space-y-2 text-sm text-slate-300">
                <li className="flex items-center gap-2">
                  <span className="inline-flex h-2 w-2 rounded-full bg-editor-accent" aria-hidden />
                  <span>Run the Vite dev server to iterate on editor views.</span>
                </li>
                <li className="flex items-center gap-2">
                  <span className="inline-flex h-2 w-2 rounded-full bg-editor-accent" aria-hidden />
                  <span>Leverage Tailwind utility classes for layout and typography.</span>
                </li>
              </ul>
            </div>
            <div>
              <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Next Steps</h3>
              <ul className="mt-2 space-y-2 text-sm text-slate-300">
                <li className="flex items-center gap-2">
                  <span className="inline-flex h-2 w-2 rounded-full bg-sky-400" aria-hidden />
                  <span>Implement shared layout and navigation components.</span>
                </li>
                <li className="flex items-center gap-2">
                  <span className="inline-flex h-2 w-2 rounded-full bg-sky-400" aria-hidden />
                  <span>Integrate API data to drive the upcoming scene list.</span>
                </li>
              </ul>
            </div>
          </div>
        </section>
      </main>
      <footer className="border-t border-slate-800 bg-editor-panel/80 px-6 py-4 text-center text-xs text-slate-500">
        Tailwind CSS is now available to accelerate building the scene editor experience.
      </footer>
    </div>
  );
};

export default App;
