from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

checker = importlib.import_module("scripts.check_agents_guidance")


def write_file(path: Path, contents: str = "sample") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents)


def test_reports_missing_guidance_when_no_agents(tmp_path, capsys):
    repo_root = tmp_path
    write_file(repo_root / "README.md")

    exit_code = checker.main(
        [
            "--repo-root",
            str(repo_root),
            "--paths",
            "README.md",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "README.md" in captured.out


def test_passes_when_ancestor_agents_present(tmp_path, capsys):
    repo_root = tmp_path
    write_file(repo_root / "Agents.md")
    write_file(repo_root / "docs" / "guide.md")

    exit_code = checker.main(
        [
            "--repo-root",
            str(repo_root),
            "--paths",
            "docs/guide.md",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "All files are covered" in captured.out


def test_respects_allowlist(tmp_path, capsys):
    repo_root = tmp_path
    write_file(repo_root / "Agents.md")
    write_file(repo_root / "build" / "artifact.txt")

    exit_code = checker.main(
        [
            "--repo-root",
            str(repo_root),
            "--paths",
            "build/artifact.txt",
            "--allowlist",
            "build",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "All files are covered" in captured.out


def test_diff_only_uses_collector(monkeypatch, tmp_path, capsys):
    repo_root = tmp_path
    write_file(repo_root / "Agents.md")
    target = repo_root / "docs" / "guide.md"
    write_file(target)

    monkeypatch.setattr(
        checker,
        "collect_changed_paths",
        lambda root: [target],
    )

    exit_code = checker.main(
        [
            "--repo-root",
            str(repo_root),
            "--diff-only",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Checked 1 file" in captured.out
