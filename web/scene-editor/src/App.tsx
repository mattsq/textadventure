import React from "react";

export const App: React.FC = () => {
  return (
    <div className="app-shell">
      <header className="app-shell__header">
        <h1>Scene Editor</h1>
        <p className="app-shell__tagline">
          Welcome to the browser-based authoring environment for text adventures.
        </p>
      </header>
      <main className="app-shell__content">
        <section>
          <h2>Getting Started</h2>
          <p>
            This placeholder interface confirms the React + TypeScript stack is configured. Subsequent
            tasks will replace this content with the actual editor experience.
          </p>
        </section>
      </main>
    </div>
  );
};

export default App;
