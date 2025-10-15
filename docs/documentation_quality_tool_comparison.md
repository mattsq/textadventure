# Documentation Spell-check and Link-check Tool Comparison

This reference deep-dives into spell-checking and link-checking solutions that
fit the documentation workflow for the text adventure project. It expands on
the automation research captured in
`docs/documentation_automation_options.md` by comparing shortlisted tools
against project-specific criteria.

## Evaluation Goals

- **Keep tooling lightweight.** Installation should work with the existing
  Python-centric environment used in CI and local development.
- **Support Markdown-first workflows.** Tools must handle the repository's
  Markdown-heavy documentation without excessive configuration.
- **Provide suppressions and custom dictionaries.** The docs include domain
  terminology (agent names, scene jargon) that needs opt-out controls.
- **Offer reliable CI automation.** Command-line interfaces must return
  non-zero exit codes on failure and play nicely with GitHub Actions caching.

## Spell-checker Comparison

| Tool | Language / Install | Strengths | Weaknesses | Local Dev Fit | CI Integration | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `codespell` | Python package (`pip install codespell`) | Mature CLI, customizable dictionary (`--dictionary`, `--ignore-words`) | English-focused, limited multi-language support | Runs via `codespell docs web README.md` with optional config file | Simple GitHub Actions step or `pre-commit` hook | Minimal dependencies align with existing tooling stack |
| `typos` | Rust binary (prebuilt release or `cargo install typos-cli`) | Fast execution, auto-suggest fixes | Requires binary download; Rust toolchain increases CI time | Local install adds non-Python dependency | Needs caching of the binary or container setup | Attractive speed but heavier maintenance burden |
| `cspell` | Node.js package (`npm install -g cspell`) | Multi-language dictionaries, VS Code integration | Pulls Node.js dependency tree, configuration more involved | Developers must manage Node-based CLI alongside Python tooling | Requires Node.js install in CI job | Overlaps with frontend stack but adds complexity outside docs scope |

### Spell-check Recommendation

- **Primary choice:** `codespell`
  - Aligns with Python tooling already documented for contributors.
  - Offers project dictionary overrides without extra services.
  - Easy to script in CI and can later be wrapped in `pre-commit`.
- **Optional consideration:** Evaluate `typos` only if `codespell` proves too
  slow at scale; currently premature given repository size.

## Link-checker Comparison

| Tool | Language / Install | Strengths | Weaknesses | Local Dev Fit | CI Integration | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `lychee` | Rust binary (`cargo install lychee` or download release) | Robust retry/backoff, config via `lychee.toml`, ignores support | Larger download (~10–15 MB); needs binary caching | Single command (`lychee --config docs/lychee.toml docs`) | Popular GitHub Action exists; binary can be cached between runs | Handles HTTP status edge cases gracefully |
| `markdown-link-check` | Node.js package/action | Zero-config GitHub Action, simple JSON config | Limited retries, slower for big repos, GitHub Action lock-in | Requires Node install for local parity | Works as dedicated workflow job but less flexible | Better suited for purely GitHub-hosted automation |
| `linkinator` | Node.js package (`npx linkinator docs`) | Streaming output, ignore patterns | No built-in retry/backoff, high noise on flaky links | Adds Node CLI dependency | Needs Node setup; lacks first-class GitHub Action | Works best when repo already standardizes on Node tooling |

### Link-check Recommendation

- **Primary choice:** `lychee`
  - Stable CLI usable both locally and in CI with the same configuration file.
  - Handles flaky external links with retry and cache controls.
  - Provides granular ignore lists to silence intentionally unreachable URLs.
- **Fallback option:** `markdown-link-check` only if avoiding Rust binaries is a
  hard requirement, acknowledging weaker retry behavior and slower runs.

## Proposed Next Steps

1. Add `codespell` to `requirements-dev.txt` (or equivalent) and craft a
   configuration file (`codespell.toml`) capturing project-specific ignores.
2. Introduce `docs/lychee.toml` to list ignored URLs, rate limits, and retry
   counts tuned for docs cadence.
3. Update the GitHub Actions workflow to run both commands alongside existing
   linting/type-check steps, ensuring failures block merges.
4. Document local usage in `docs/contributing.md`, providing sample commands and
   how to update ignore lists when new jargon appears.

