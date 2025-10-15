"""Validate that repository files are covered by scoped AGENTS.md guidance."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Set

DEFAULT_ALLOWLIST = {".git", "__pycache__"}


@dataclass(frozen=True)
class CheckResult:
    missing: List[Path]
    checked: List[Path]

    @property
    def is_success(self) -> bool:
        return not self.missing


def discover_agent_directories(repo_root: Path) -> Set[Path]:
    agent_dirs: Set[Path] = set()
    for path in repo_root.rglob("*"):
        if path.is_file() and path.name.lower() == "agents.md":
            agent_dirs.add(path.parent.resolve())
    return agent_dirs


def normalize_allowlist(repo_root: Path, allowlist: Sequence[str]) -> Set[Path]:
    normalized: Set[Path] = set()
    for entry in allowlist:
        entry_path = (repo_root / entry).resolve()
        normalized.add(entry_path)
    return normalized


def is_allowlisted(path: Path, allowlist: Set[Path], repo_root: Path) -> bool:
    absolute = path.resolve()
    for allowed in allowlist:
        try:
            absolute.relative_to(allowed)
            return True
        except ValueError:
            continue
    return False


def find_missing_guidance(
    files: Iterable[Path],
    agent_dirs: Set[Path],
    repo_root: Path,
    allowlist: Set[Path],
) -> CheckResult:
    missing: List[Path] = []
    checked: List[Path] = []
    for file_path in files:
        if not file_path.exists():
            # Deleted files or missing paths are skipped.
            continue
        if file_path.name.lower() == "agents.md":
            continue
        absolute_path = file_path.resolve()
        checked.append(absolute_path)
        if is_allowlisted(absolute_path, allowlist, repo_root):
            continue
        current = absolute_path.parent
        has_guidance = False
        while True:
            if current in agent_dirs:
                has_guidance = True
                break
            if current == repo_root:
                break
            current = current.parent
        if not has_guidance and repo_root in agent_dirs:
            has_guidance = True
        if not has_guidance:
            missing.append(absolute_path.relative_to(repo_root))
    return CheckResult(missing=missing, checked=checked)


def _run_git_command(repo_root: Path, args: Sequence[str]) -> List[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Git command failed: git {' '.join(args)}\n{completed.stderr.strip()}"
        )
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def collect_changed_paths(repo_root: Path) -> List[Path]:
    paths: List[str] = []
    for diff_args in (
        ["diff", "--name-only", "--diff-filter=ACMRTUXB"],
        ["diff", "--name-only", "--diff-filter=ACMRTUXB", "--staged"],
    ):
        paths.extend(_run_git_command(repo_root, diff_args))
    unique_paths = sorted({p for p in paths})
    return [repo_root / path for path in unique_paths]


def collect_all_tracked_paths(repo_root: Path) -> List[Path]:
    paths = _run_git_command(repo_root, ["ls-files"])
    return [repo_root / path for path in paths]


def parse_arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ensure files are covered by scoped AGENTS.md guidance.",
    )
    parser.add_argument(
        "--repo-root",
        default=Path.cwd(),
        type=Path,
        help="Repository root. Defaults to the current working directory.",
    )
    parser.add_argument(
        "--allowlist",
        action="append",
        default=[],
        help="Relative paths that are exempt from guidance checks.",
    )
    parser.add_argument(
        "--diff-only",
        action="store_true",
        help="Only check files changed in the current working tree (staged and unstaged).",
    )
    parser.add_argument(
        "--paths",
        nargs="*",
        help="Explicit file paths to check (relative to the repo root). Overrides diff/all detection.",
    )
    parser.add_argument(
        "--format",
        choices=("human", "json"),
        default="human",
        help="Output format for reporting results.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_arguments(argv)
    repo_root = args.repo_root.resolve()
    if not repo_root.exists():
        raise SystemExit(f"Repository root does not exist: {repo_root}")

    allowlist = normalize_allowlist(
        repo_root, list(DEFAULT_ALLOWLIST) + list(args.allowlist)
    )

    if args.paths:
        target_paths = [repo_root / Path(p) for p in args.paths]
    elif args.diff_only:
        target_paths = collect_changed_paths(repo_root)
    else:
        target_paths = collect_all_tracked_paths(repo_root)

    agent_dirs = discover_agent_directories(repo_root)
    result = find_missing_guidance(target_paths, agent_dirs, repo_root, allowlist)

    missing_rel = [str(path) for path in result.missing]
    checked_count = len(result.checked)

    if args.format == "json":
        payload = {
            "checked_file_count": checked_count,
            "missing_count": len(missing_rel),
            "missing_files": missing_rel,
            "allowlist": [
                str(path.relative_to(repo_root)) for path in allowlist if path.exists()
            ],
            "status": "success" if result.is_success else "failure",
        }
        print(json.dumps(payload, indent=2))
    else:
        print(f"Checked {checked_count} file(s) for AGENTS.md coverage.")
        if result.is_success:
            print("All files are covered by scoped guidance.")
        else:
            print("The following files lack AGENTS.md coverage:")
            for missing in missing_rel:
                print(f"  - {missing}")

    return 0 if result.is_success else 1


if __name__ == "__main__":
    sys.exit(main())
