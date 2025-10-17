# Rich Text Editor Framework Evaluation

## Purpose
The scene editor requires a rich text surface that lets authors compose narrative
copy with Markdown-compatible formatting while fitting within our collaboration
and persistence constraints. This document summarises the evaluation of the most
viable React-based frameworks and captures the rationale for the recommended
choice moving forward.

## Evaluation Criteria
The following criteria were used to assess each framework:

1. **Markdown Support** – Ability to emit clean Markdown or provide extensible
   serializers so our backend can continue storing text-based diffs.
2. **Collaboration Hooks** – APIs for multi-user presence, comments, and shared
   cursors without rebuilding the editor from scratch.
3. **Extensibility** – Plugin architecture that lets us add custom node types
   (e.g. command callouts) and validation rules aligned with adventure-specific
   requirements.
4. **Accessibility** – Keyboard navigation, ARIA attributes, and screen-reader
   compatibility.
5. **Documentation & Community** – Quality of guides, ecosystem maturity, and
   active maintenance cadence.
6. **Bundle Size & Performance** – Ability to lazily load heavy dependencies and
   keep the editor responsive in long scenes.
7. **Licensing** – OSS-friendly licence compatible with the project’s Apache 2.0
   distribution.

## Candidate Comparison

| Framework | Markdown Story | Collaboration Story | Extensibility | Accessibility | Maintenance Snapshot |
| --- | --- | --- | --- | --- | --- |
| **TipTap (ProseMirror)** | First-party Markdown extension with round-trip serialisation and schema customisation. | Community-maintained Y.js bindings plus TipTap Collaboration Kit for cursors/presence. | Strong – schema driven nodes/marks, custom commands, input rules. | Good – ProseMirror exposes ARIA hooks; TipTap docs cover keyboard shortcuts. | Active (v2, weekly releases, strong Discord/GitHub support). |
| **Slate.js** | Requires third-party plugins for Markdown export; serialisation brittle for nested marks. | No official solution; community packages for Y.js exist but require manual plumbing. | Flexible JSON AST model; custom elements straightforward. | Solid keyboard support but ARIA patterns require manual wiring. | Stable but slower release cadence; core team prioritises backward compatibility. |
| **Lexical (Meta)** | Markdown export provided via transform plugins but limited formatting options without custom work. | Lexical Collaboration (with Y.js) still experimental; documentation thin. | Modular nodes and commands; rich plugin ecosystem emerging. | Excellent focus on accessibility and screen readers. | Active releases, but project is still 1.x with occasional breaking changes. |
| **Remirror** | Built on ProseMirror with Markdown preset; serialisation reliable. | Yjs extension maintained by core team; collaborative editor examples available. | High – preset architecture and SSR support. | Good – inherits ProseMirror semantics; docs emphasise ARIA compliance. | Moderate – steady updates though smaller community than TipTap. |

## Detailed Findings

### TipTap
- Built on top of ProseMirror, giving access to a battle-tested document model.
- Markdown extension supports both import and export. Schemas can be restricted
  to our approved mark set, preventing unsupported formatting from reaching the
  backend.
- Offers first-party collaboration helpers (cursor presence, history syncing) and
  integrates cleanly with Y.js for conflict resolution.
- Plugin ecosystem includes bubble menus, slash commands, and character count
  extensions that map well to adventure authoring needs.
- Comprehensive TypeScript types and active maintainers reduce the long-term
  maintenance burden.

### Slate.js
- JSON AST is approachable but lacks canonical Markdown tooling. Existing
  packages such as `slate-md-serializer` struggle with complex mark nesting,
  which would increase QA overhead.
- Collaboration requires manually wiring Slate operations through Y.js or other
  CRDT layers. Example implementations exist but are under-documented.
- Strength lies in lower-level control; however, that would increase the amount
  of editor infrastructure we need to own.

### Lexical
- Impressive performance characteristics and a modern API, yet Markdown support
  relies on composing separate transform plugins. Advanced Markdown features
  (tables, nested lists) need additional development.
- Collaboration plugins are marked experimental; stability is not yet battle
  tested for production authoring environments.
- Strong accessibility guarantees make Lexical attractive, but the relative
  infancy of ecosystem tooling introduces risk for our timeline.

### Remirror
- Provides a curated set of extensions on top of ProseMirror with good Markdown
  support out of the box.
- Documentation is improving but still thinner than TipTap’s. Examples for
  collaboration are available but less comprehensive, raising onboarding costs.
- Offers SSR support and React bindings similar to TipTap, but the smaller
  community could slow bug fixes.

## Recommendation
Adopt **TipTap** as the primary rich text framework. It balances mature
Markdown tooling, strong collaboration integrations, and an active community.
Because it shares a ProseMirror foundation with Remirror, we retain flexibility
to reuse community extensions if needed. TipTap’s TypeScript-first API aligns
with the existing scene editor stack and keeps custom node/mark development
straightforward.

## Implementation Notes
- Restrict the editor schema to headings, paragraphs, emphasis, lists, inline
  code, and block quotes to match the CLI Markdown renderer.
- Use the TipTap Markdown extension for round-trip serialisation; add automated
  tests to ensure fidelity with the Python renderer.
- Integrate the Collaboration Kit backed by Y.js to reuse the existing presence
  service introduced in the collaboration slice.
- Lazy-load heavy plugins (Markdown, collaboration) so the base editor shell
  remains responsive when navigating between scenes.

## Next Steps
1. Prototype the TipTap editor instance inside the existing scene editor form
   and validate Markdown serialisation against the backend API.
2. Wire Y.js collaboration providers to our collaboration session API and reuse
   existing presence indicators.
3. Define automated tests covering Markdown round-trips, toolbar shortcuts, and
  multi-user editing edge cases (conflicting marks, undo/redo across clients).
4. Update developer documentation with integration patterns and troubleshooting
   tips once the prototype stabilises.
