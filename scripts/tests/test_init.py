"""Tests for the new-crate template and its local metadata updates."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from importlib.resources import as_file
from pathlib import Path

import pytest
import tomlkit
from typer.testing import CliRunner

from qproj_scripts import init
from qproj_scripts._common import run
from qproj_scripts.cli import app


@pytest.mark.parametrize(
    "bin_, crate_root", [(False, Path("src/lib.rs")), (True, Path("src/main.rs"))]
)
def test_render_project(tmp_path: Path, bin_: bool, crate_root: Path) -> None:
    dest = tmp_path / "q_cam"
    name, bevy_version = "q_cam", "9.99"
    init._render_project(name, dest, bevy_version, bin_=bin_, dry=False)

    with as_file(init.asset("project-template")) as template:
        expected = {
            src.relative_to(template): src
            for src in template.rglob("*")
            if src.is_file()
            and (
                src.relative_to(template).parts[0] != "src"
                or src.relative_to(template) == crate_root
            )
        }
        assert crate_root in expected
        assert {p.relative_to(dest) for p in dest.rglob("*") if p.is_file()} == expected.keys()
        assert any(b"{{name}}" in src.read_bytes() for src in expected.values())
        assert any(b"{{bevy_version}}" in src.read_bytes() for src in expected.values())
        for rel, src in expected.items():
            rendered = (
                src.read_bytes()
                .replace(b"{{name}}", name.encode())
                .replace(b"{{bevy_version}}", bevy_version.encode())
            )
            assert (dest / rel).read_bytes() == rendered


def test_registry_and_workspace_updates_are_idempotent(tmp_path: Path) -> None:
    target = tmp_path / "assets" / "downstream-repos.json"
    target.parent.mkdir()
    target.write_text("[]\n")
    registry = tmp_path / "downstream-repos.json"
    registry.symlink_to(target.relative_to(registry.parent))
    assert init._append_registry(registry, "cubething-qproj/q_cam")
    assert not init._append_registry(registry, "cubething-qproj/q_cam")
    assert json.loads(target.read_text()) == ["cubething-qproj/q_cam"]

    workspace = tmp_path / "Cargo.toml"
    workspace.write_text('[workspace]\nmembers = ["lib/*"]\n')
    dest = tmp_path / "lib/q_cam"
    init._patch_workspace("q_cam", dest, workspace, dry=False)
    first = workspace.read_text()
    init._patch_workspace("q_cam", dest, workspace, dry=False)
    assert workspace.read_text() == first
    patch = tomlkit.parse(first)["patch"]["https://github.com/cubething-qproj/q_cam"]
    assert patch["q_cam"]["path"] == "lib/q_cam"


def test_register_uses_separate_worktree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    remote, repo = tmp_path / "remote.git", tmp_path / "infra"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "init", "-b", "main", str(repo)], check=True)
    for args in (
        ("config", "user.name", "Test User"),
        ("config", "user.email", "test@example.com"),
        ("config", "commit.gpgsign", "false"),
        ("remote", "add", "origin", str(remote)),
    ):
        run(["git", "-C", str(repo), *args])
    target = repo / "assets/downstream-repos.json"
    target.parent.mkdir()
    target.write_text("[]\n")
    registry = repo / "downstream-repos.json"
    registry.symlink_to("assets/downstream-repos.json")
    run(["git", "-C", str(repo), "add", "."])
    run(["git", "-C", str(repo), "commit", "-m", "initial"])
    run(["git", "-C", str(repo), "push", "-u", "origin", "main"])

    (repo / "local.txt").write_text("keep this\n")
    gh_calls: list[list[str]] = []

    def fake_run(
        cmd: Sequence[str], *, dry: bool = False, capture_output: bool = False
    ) -> subprocess.CompletedProcess[str] | None:
        if cmd[0] == "gh":
            gh_calls.append(list(cmd))
            return subprocess.CompletedProcess(list(cmd), 0, stdout="")
        return run(cmd, dry=dry, capture_output=capture_output)

    monkeypatch.setattr(init, "run", fake_run)
    init._register("q_cam", registry, dry=False)

    assert target.read_text() == "[]\n"
    assert (repo / "local.txt").read_text() == "keep this\n"
    registered = subprocess.run(
        ["git", "-C", str(repo), "show", "automation/init-crate:assets/downstream-repos.json"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout
    assert json.loads(registered) == ["cubething-qproj/q_cam"]
    assert [cmd[:3] for cmd in gh_calls] == [["gh", "pr", "list"], ["gh", "pr", "create"]]
    worktrees = subprocess.run(
        ["git", "-C", str(repo), "worktree", "list", "--porcelain"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout
    assert worktrees.count("worktree ") == 1


@pytest.mark.parametrize("name", ["lib/q_cam", "../q_cam", "q-cam", ""])
def test_invalid_names_do_not_create_a_crate(tmp_path: Path, name: str) -> None:
    dest = tmp_path / "new_crate"
    result = CliRunner().invoke(
        app,
        ["init", name, "--lib", "--dest", str(dest), "--bevy-version", "0.19", "-x"],
    )
    assert result.exit_code != 0
    assert not dest.exists()
