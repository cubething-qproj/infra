"""Behavior tests for ordinary-checkout synchronization."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from qproj_scripts import sync


def _git(path: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(path), *args], check=True)


def test_sync_repo_preserves_ordinary_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = tmp_path / "repos"
    remote = tmp_path / "remote.git"
    seed = tmp_path / "seed"
    repo = base / "example" / "demo"
    config = tmp_path / "config"
    assets = tmp_path / "assets" / ".config"

    subprocess.run(["git", "init", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "clone", str(remote), str(seed)], check=True)
    _git(seed, "config", "user.name", "Test User")
    _git(seed, "config", "user.email", "test@example.com")
    (seed / "README.md").write_text("demo\n")
    _git(seed, "add", "README.md")
    _git(seed, "-c", "commit.gpgsign=false", "commit", "-m", "chore: seed")
    _git(seed, "push", "-u", "origin", "main")
    repo.parent.mkdir(parents=True)
    subprocess.run(["git", "clone", str(remote), str(repo)], check=True)

    config.mkdir()
    (config / "AGENTS.md").write_text("shared\n")
    assets.mkdir(parents=True)
    (assets / "AGENTS.md").write_text("asset\n")
    monkeypatch.setattr(sync, "asset", lambda _path: assets)

    sync._sync_repo("example/demo", base, config, dry=False)

    assert (repo / ".git").is_dir()
    assert len(_git_output(repo, "worktree", "list", "--porcelain").split("worktree ")) == 2
    assert (repo / "AGENTS.md").resolve() == config / "AGENTS.md"
    assert "/AGENTS.md" in (repo / ".git" / "info" / "exclude").read_text()


def _git_output(path: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(path), *args], capture_output=True, text=True, check=True
    ).stdout
