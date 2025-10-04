# Contributing Guidelines

These guidelines outline the expectations for contributing to the Text Adventure Agent Playground.
They consolidate the project conventions already used throughout the repository and provide a
checklist you can follow before opening a pull request.

## Getting Started

1. **Fork and clone** the repository or create a development branch off `main` if you have write
   access.
2. **Create a virtual environment** with Python 3.9 or newer:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```
3. **Install dependencies** required for development and testing:
   ```bash
   pip install -r requirements.txt
   ```
4. **Run the existing test suite** once to confirm your environment is configured correctly:
   ```bash
   pytest -q
   ```

## Workflow Expectations

- Keep branches focused on a single feature or bugfix. Use descriptive branch names such as
  `feature/analytics-reporting` or `fix/save-session-reset`.
- Write commits in the **imperative mood** (for example, `Add persistence helper`). Squash commits
  only if doing so keeps the history easy to follow.
- Reference GitHub issues where possible using `Fixes #123` or `Refs #456` in the commit or PR
  description.
- Open a draft pull request early if you want feedback. Update the PR description to summarise the
  motivation, list key changes, and flag follow-up work.

## Code Quality Checklist

Every change should pass the same gates enforced in CI. Run these commands before committing:

```bash
pytest -q
mypy src
ruff check src tests
black --check src tests
```

If you modify files outside `src/` or `tests/`, extend the commands accordingly (for example, run
`ruff` or `black` on additional directories). Fix warnings and style violations rather than
suppressing them.

## Testing Guidelines

- Add or update tests under `tests/` for any new feature, bug fix, or regression scenario.
- Use the existing pytest fixtures (such as the mock LLM clients) to keep tests deterministic.
- Prefer unit tests that cover narrow components; add integration tests when behaviour spans multiple
  modules (e.g., CLI workflows or persistence round-trips).
- When introducing new data files, include fixture content in `tests/data/` to keep tests
  self-contained.

## Documentation & Examples

- Update `README.md` or the relevant document under `docs/` when introducing new features or workflow
  changes.
- Add inline docstrings when public classes or functions change behaviour. The repository uses
  standard Python docstring conventions; keep them concise and actionable.
- Provide examples or command snippets where helpful so other contributors can reproduce your setup
  or validate the behaviour.

## Pull Request Review Process

- Ensure your branch is up to date with `main` before requesting review. Resolve merge conflicts
  locally and rerun the quality checks afterwards.
- Use clear PR titles in the imperative mood and provide a short summary plus testing notes in the
  description.
- Respond to review feedback promptly. When addressing feedback, mention the reviewer and summarise
  the changes to confirm the resolution.
- After merging, delete your branch unless it is tracking long-running work.

Following these practices keeps the project consistent and makes it easier for maintainers to review
and merge contributions.
