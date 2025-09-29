# Rich Text Narration Editor Plan

## Overview
The story-authoring backlog includes a rich text editor so narrative copy can be
composed with formatting cues (emphasis, lists, inline callouts) rather than
plain strings inside `scripted_scenes.json`. This document captures the current
content pipeline, the functional requirements for the editor, and a phased
implementation strategy that aligns with the existing Python backend.

## Current Authoring Workflow
- Scene narration is stored as plain strings within JSON scene definitions
  (e.g. `src/textadventure/data/scripted_scenes.json`).
- Authors typically edit the JSON manually or through simple text fields in
  prototype UIs.
- Narration is rendered verbatim by the scripted story engine, so any desired
  emphasis must be encoded with ad-hoc punctuation or all caps.
- The CLI consumer renders narration linearly without awareness of formatting
  metadata.

## Editor Goals and Requirements
1. **Formatting Capabilities** – Bold, italic, underline, headings, bullet
   lists, and inline code/quote callouts cover the common author requests. The
   editor should also support hyperlinks for lore references.
2. **Content Safety** – Restrict formatting to a safe subset (e.g. Markdown or
   HTML sanitised on save) to avoid breaking consumers.
3. **Preview Fidelity** – Provide a side-by-side or inline preview that matches
   the runtime renderer so authors can confirm spacing and emphasis.
4. **Keyboard Accessibility** – Support shortcuts (Ctrl/Cmd+B/I/U) and basic
   tab navigation in line with the later accessibility backlog items.
5. **Version Control Friendly** – Persist changes in a text-based format so diffs
   remain readable in Git reviews.
6. **Extensibility** – Keep the architecture open for future plugins, such as
   inline annotations from QA reviewers or automated quality checks.

## Data Model & Persistence Plan
- Adopt CommonMark-flavoured Markdown as the storage format. Markdown is
  already friendly to diffing and can be rendered consistently on the CLI by
  parsing to ANSI formatting.
- Update scene schemas to record narration as Markdown strings plus optional
  metadata fields (e.g. `format: "markdown"`). Existing scenes remain valid by
  defaulting to plain text.
- Extend loaders and validators so Markdown is normalised (strip trailing
  whitespace, ensure heading levels begin at `##` to avoid nested document
  structure issues).
- Provide helper functions in `scripted_story_engine.py` to render Markdown to
  plain text or ANSI-enhanced output depending on the client.

## Integration Strategy
1. **Editor Foundation** – Choose a web-based rich text component that outputs
   Markdown, such as TipTap with the Markdown extension or a Slate.js wrapper.
   Encapsulate it within the upcoming authoring UI shell so it can reuse global
   state management.
2. **State Synchronisation** – Bind editor state to the scene form store.
   Auto-save drafts locally (localStorage) and expose explicit save actions that
   write to JSON via the backend API.
3. **Rendering Pipeline** – Implement a shared Markdown renderer package (likely
   using `markdown-it` in the front-end and `markdown-it-py` on the backend) to
   guarantee consistent preview and runtime output.
4. **Validation** – Hook into existing validation flows to flag unsupported
   constructs (e.g. tables) and warn about exceeding recommended length.
5. **Testing** – Add unit tests for Markdown parsing round-trips plus Cypress
   (or Playwright) coverage exercising formatting shortcuts, toolbar actions,
   and persistence.

## Incremental Milestones
1. Document requirements and system design (this document).
2. Spike Markdown rendering in the existing CLI to ensure narrative output looks
   correct with ANSI styling.
3. Scaffold the web authoring shell with the selected editor component and wire
   it to the scene schema.
4. Add collaborative niceties (presence indicators, inline comments) once the
   baseline editor is stable.

## Open Questions
- Should narrated Markdown allow embedded variables/macros for dynamic data?
- How should we migrate legacy plain-text scenes—auto-wrap as Markdown or allow
  per-scene opt-in?
- Do we need a read-only mode for reviewers separate from authors?

## Next Steps
- Validate the Markdown rendering approach in the Python runtime and document
  any limitations.
- Prototype the editor component within the planned authoring UI layout.
- Gather feedback from content designers on desired toolbar defaults and
  keyboard shortcuts before finalising the UX.
