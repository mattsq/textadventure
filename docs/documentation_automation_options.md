# Documentation Automation Options

This note captures candidate tools and integration strategies for automating documentation hygiene checks in CI. The focus areas come from Phase 4 of the documentation expansion plan: enforcing scoped `AGENTS.md` coverage and catching documentation regressions (spelling or broken links).

## Enforcing Scoped `AGENTS.md` Coverage

### Goals
- Warn contributors when files within a directory tree lack a corresponding `AGENTS.md`.
- Prevent regressions where nested `AGENTS.md` files are deleted or miss required guidance.
- Keep the solution lightweight so it can run in the existing GitHub Actions matrix.

### Candidate Approaches
1. **Custom Python checker executed in CI**
   - Traverse the repository and build a directory map of required `AGENTS.md` coverage.
   - Validate that each committed file has guidance in its nearest ancestor `AGENTS.md`.
   - Pros: Totally configurable, can share logic with the existing tooling stack.
   - Cons: Requires ongoing maintenance; needs unit tests.
2. **Pre-commit hook with `check-ast`-style plugin**
   - Ship a script under `scripts/check_agents_guidance.py` and wire it into a `pre-commit` configuration.
   - Pros: Gives developers immediate feedback locally; can be reused in CI (`pre-commit run --all-files`).
   - Cons: Introduces a new dependency (`pre-commit`) and requires contributor onboarding updates.
3. **Documented manual checklist**
   - Extend the PR template and `docs/contributing.md` with an explicit checkbox for AGENT coverage.
   - Pros: Zero technical overhead.
   - Cons: Relies on human diligence; less reliable than automated checks.

### Recommendation
Start with the **custom Python checker** because it keeps dependencies minimal and can be invoked via `python -m scripts.check_agents` in CI. Pair it with guidance in the PR template so reviewers know the expectation. The checker can emit structured output that highlights missing scope coverage and fail the build when issues appear.

## Documentation Spell-check and Link-check

### Goals
- Catch typos across Markdown documents.
- Ensure internal and external hyperlinks remain valid.
- Integrate smoothly with the Python-based toolchain.

### Candidate Tools
1. **`codespell` for spelling**
   - Lightweight CLI that scans files using a curated dictionary.
   - Supports ignore lists for project-specific terminology.
   - Easy to install via `pip` and fast enough for CI.
2. **`typos` (Rust-based)**
   - Finds spelling mistakes with language-aware heuristics.
   - Pros: Faster than Python alternatives, includes built-in dictionary.
   - Cons: Requires Rust binary download in CI; heavier footprint.
3. **`lychee` for link checking**
   - CLI that validates HTTP links and local file references inside Markdown.
   - Supports configuration files (`lychee.toml`) for ignores and retries.
4. **`markdown-link-check` GitHub Action**
   - Simple to wire but adds an extra job invocation per run.
   - Less configurable and slower for large repos.

### Recommended Combination
- Add `codespell` to the Python requirements and run it alongside Ruff/Black in CI.
- Configure `lychee` as a step in the docs workflow, using a curated ignore list for intentionally offline targets.
- Document overrides in `docs/contributing.md` so contributors know how to run the checks locally (`codespell docs web README.md`, `lychee --config docs/lychee.toml docs`).

## Next Steps
- Prototype the `AGENTS.md` checker script under `scripts/` with unit tests in `tests/scripts/`.
- Draft CI updates (GitHub Actions workflow snippet) to call the checker, `codespell`, and `lychee`.
- Update onboarding docs with the new commands once the automation lands.
