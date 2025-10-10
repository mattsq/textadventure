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
npm run dev      # start the Vite development server
```

Additional scripts:

- `npm run build` – Generate an optimized production build under `dist/`.
- `npm run preview` – Serve the production build locally for smoke testing.
- `npm run typecheck` – Validate the TypeScript configuration and component
  types without running the bundler.

The project now uses the Vite + React toolchain, providing fast hot-module
replacement during development and a production-ready bundling pipeline for
future feature work.
