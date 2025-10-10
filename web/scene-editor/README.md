# Scene Editor Frontend

This package contains the browser-based editor UI that complements the FastAPI
backend exposed by the text adventure runtime. The initial scaffolding focuses
on providing a TypeScript-enabled React application so future tasks can layer in
the build tooling, routing, state management, and feature views described in the
Priority 10 roadmap.

## Getting Started

```bash
cd web/scene-editor
npm install
npm run typecheck
```

Running `npm run typecheck` ensures the TypeScript configuration is valid and
all React components type-check correctly. Build tooling, development servers,
and runtime integration will be added in follow-up tasks.
