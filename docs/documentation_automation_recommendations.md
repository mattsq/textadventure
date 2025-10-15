# Documentation Automation Recommendations

This guide turns the research in `docs/documentation_automation_options.md` and `docs/documentation_quality_tool_comparison.md` into a concrete adoption plan. The goal is to introduce lightweight CI and local tooling that keeps contributor guidance accurate while preventing regressions in the Markdown knowledge base.

## Recommended Tooling Stack

1. **Scoped `AGENTS.md` coverage checker**
   - Implement a Python CLI under `scripts/check_agents_guidance.py` that inspects staged or committed files and validates that each file resides beneath an `AGENTS.md` with relevant scope.
   - Provide flags for repository root (default: project root), allowlist paths (for directories intentionally exempt), and a `--diff-only` mode for faster local runs.
   - Emit structured JSON and human-readable summaries so GitHub Actions can both fail the job and annotate missing coverage in workflow logs.
2. **Spelling guardrail with `codespell`**
   - Add `codespell` to `requirements.txt` or a new `requirements-dev.txt` entry and pin the version for deterministic CI.
   - Store project-specific jargon in `docs/codespell-ignore-words.txt` and reference it from a minimal `codespell.toml`.
   - Default command: `codespell --toml docs/codespell.toml docs web README.md`.
3. **Link validation with `lychee`**
   - Vendor a `docs/lychee.toml` that defines retry counts, per-domain rate limits, and ignore lists for localhost or deliberately unreachable URLs.
   - Download the prebuilt binary in CI and cache it using the GitHub Actions tool cache to avoid repeated installs.
   - Default command: `lychee --config docs/lychee.toml docs web README.md`.

## Integration Roadmap

1. **Prototype Phase**
   - Build the `check_agents_guidance.py` script with unit coverage in `tests/scripts/test_check_agents_guidance.py`.
   - Draft configuration files for `codespell` and `lychee`; circulate with documentation stewards for jargon/URL confirmation.
   - Run the tools manually on the current repository snapshot to surface existing violations and tune ignore lists.
2. **CI Adoption Phase**
   - Extend the existing GitHub Actions workflow to execute:
     ```yaml
     - name: Validate documentation guardrails
       run: |
         python -m scripts.check_agents_guidance --diff-only
         codespell --toml docs/codespell.toml docs web README.md
         lychee --config docs/lychee.toml docs web README.md
     ```
   - Promote `--diff-only` to `--all-files` once initial cleanup completes.
   - Fail the workflow on any reported issues, and surface actionable summaries in the job logs.
3. **Contributor Enablement Phase**
   - Update `docs/contributing.md` and `docs/getting_started.md` with installation and usage notes for the new commands.
   - Add PR template checkboxes reminding authors to run the documentation guardrails before requesting review.
   - Offer optional `pre-commit` hooks mirroring the CI commands for contributors who prefer automated local checks.

## Success Metrics and Follow-up

- **Baseline adoption:** All CI jobs fail when documentation guardrails detect issues, and developers know how to resolve them via the updated docs.
- **Trend monitoring:** Track the number of violations caught per month to evaluate whether ignore lists need refinement or new documentation areas require scoped `AGENTS.md` guidance.
- **Future enhancements:** Once the guardrails are stable, explore incremental improvements such as auto-fixing trivial `codespell` suggestions or caching `lychee` results between runs.

Use this document as the reference point when implementing the automation tasks and when new contributors ask for the rationale behind the tooling choices.
