"""Scaffold a crate in a caller-specified directory. Dry-run unless ``-x`` is passed."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from importlib.resources import as_file
from pathlib import Path

import tomlkit
import typer

from qproj_scripts import bevy_lint, clippy, test
from qproj_scripts._common import DEFAULT_BRANCH, DEFAULT_REMOTE, asset, log, run

ORG = "cubething-qproj"
_INIT_BRANCH = "automation/init-crate"
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


def _render_project(name: str, dest: Path, bevy_version: str, *, bin_: bool, dry: bool) -> None:
    """Copy the template, keeping only the selected crate root under src/."""
    selected = Path("src/main.rs" if bin_ else "src/lib.rs")
    with as_file(asset("project-template")) as template:
        for src in sorted(template.rglob("*")):
            if not src.is_file():
                continue
            rel = src.relative_to(template)
            if rel.parts[0] == "src" and rel != selected:
                continue
            dst = dest / rel
            log(f"copy {src} -> {dst}", level="dry" if dry else "info")
            if dry:
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            data = src.read_bytes()
            rendered = data.replace(b"{{name}}", name.encode()).replace(
                b"{{bevy_version}}", bevy_version.encode()
            )
            if data == rendered:
                shutil.copyfile(src, dst)
            else:
                dst.write_bytes(rendered)


def _bootstrap_in_place(
    name: str, repo_dir: Path, *, create_remote: bool, private: bool, dry: bool
) -> None:
    """Initialize the scaffold as a repository and optionally publish it."""
    run(["git", "init", "-b", DEFAULT_BRANCH, str(repo_dir)], dry=dry)
    run(["git", "-C", str(repo_dir), "add", "."], dry=dry)
    run(["git", "-C", str(repo_dir), "commit", "-m", "chore: initial commit"], dry=dry)
    if create_remote:
        full = f"{ORG}/{name}"
        run(["gh", "repo", "create", full, "--private" if private else "--public"], dry=dry)
        run(
            [
                "git",
                "-C",
                str(repo_dir),
                "remote",
                "add",
                DEFAULT_REMOTE,
                f"git@github.com:{full}.git",
            ],
            dry=dry,
        )
        run(["git", "-C", str(repo_dir), "push", "-u", DEFAULT_REMOTE, DEFAULT_BRANCH], dry=dry)


def _append_registry(registry: Path, full: str) -> bool:
    repos = json.loads(registry.read_text())
    if full in repos:
        return False
    registry.write_text(json.dumps([*repos, full], indent=2) + "\n")
    return True


def _register(name: str, registry: Path, *, dry: bool) -> None:
    """Open/update a PR from origin/main without modifying the infra checkout."""
    full = f"{ORG}/{name}"
    repo = subprocess.run(
        ["git", "-C", str(registry.parent), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    relative = registry.absolute().relative_to(Path(repo))
    run(["git", "-C", repo, "fetch", DEFAULT_REMOTE], dry=dry)
    if dry:
        log(
            f"worktree from {DEFAULT_REMOTE}/{DEFAULT_BRANCH}: add {full}, commit, "
            f"push --force {_INIT_BRANCH}, create/update PR, remove worktree in {repo}",
            level="dry",
        )
        return
    with tempfile.TemporaryDirectory(prefix="qproj-init-") as temp:
        checkout = Path(temp) / "infra"
        run(
            [
                "git",
                "-C",
                repo,
                "worktree",
                "add",
                "-B",
                _INIT_BRANCH,
                str(checkout),
                f"{DEFAULT_REMOTE}/{DEFAULT_BRANCH}",
            ],
        )
        try:
            target = (checkout / relative).resolve()
            if not target.is_relative_to(checkout):
                raise ValueError(f"registry symlink points outside the infra checkout: {target}")
            if not _append_registry(target, full):
                log(f"{full} already registered on {DEFAULT_REMOTE}/{DEFAULT_BRANCH}", level="info")
                return
            run(["git", "-C", str(checkout), "add", str(target.relative_to(checkout))])
            run(["git", "-C", str(checkout), "commit", "-m", f"chore: register {name}"])
            run(["git", "-C", str(checkout), "push", "--force", DEFAULT_REMOTE, _INIT_BRANCH])
            existing = run(
                [
                    "gh",
                    "pr",
                    "list",
                    "--repo",
                    f"{ORG}/infra",
                    "--head",
                    _INIT_BRANCH,
                    "--json",
                    "number",
                    "-q",
                    ".[0].number",
                ],
                capture_output=True,
            )
            assert existing is not None
            if not existing.stdout.strip():
                run(
                    [
                        "gh",
                        "pr",
                        "create",
                        "--repo",
                        f"{ORG}/infra",
                        "--head",
                        _INIT_BRANCH,
                        "--base",
                        DEFAULT_BRANCH,
                        "--title",
                        f"chore: register {name}",
                        "--body",
                        f"Register {full} as a downstream repository.",
                    ],
                )
        finally:
            run(["git", "-C", repo, "worktree", "remove", "--force", str(checkout)])


def _patch_workspace(name: str, dest: Path, workspace: Path, *, dry: bool) -> None:
    """Make Git dependencies on a new library resolve to its local checkout."""
    rel = dest.resolve().relative_to(workspace.parent.resolve())
    url = f"https://github.com/{ORG}/{name}"
    document = tomlkit.parse(workspace.read_text())
    if "patch" in document and url in document["patch"]:
        return
    log(f"patch {workspace}: {url} = {rel}", level="dry" if dry else "info")
    if dry:
        return
    if "patch" not in document:
        document["patch"] = tomlkit.table()
    entry = tomlkit.inline_table()
    entry["path"] = rel.as_posix()
    document["patch"][url] = {name: entry}
    workspace.write_text(tomlkit.dumps(document))


def _validate(name: str, dest: Path, bevy_version: str, workspace: Path | None) -> None:
    if not _NAME.fullmatch(name):
        raise typer.BadParameter("name must be a bare Rust identifier")
    if not re.fullmatch(r"\d+\.\d+(?:\.\d+)?", bevy_version):
        raise typer.BadParameter("bevy version must be a numeric version (e.g. 0.19)")
    if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
        raise typer.BadParameter(f"{dest} already exists and is non-empty")
    if workspace is not None:
        if not workspace.is_file():
            raise typer.BadParameter(f"workspace manifest not found: {workspace}")
        if not dest.resolve().is_relative_to(workspace.parent.resolve()):
            raise typer.BadParameter("destination must be inside the workspace")


def main(
    name: str = typer.Argument(..., help="Crate name, e.g. q_cam."),
    bin_: bool = typer.Option(False, "--bin", help="Create a binary crate."),
    lib: bool = typer.Option(False, "--lib", help="Create a library crate."),
    dest: Path = typer.Option(..., "--dest", help="Target directory."),
    bevy_version: str = typer.Option(..., "--bevy-version", help="Version for template tokens."),
    registry: Path | None = typer.Option(None, "--registry", help="Infra downstream-repos.json."),
    workspace: Path | None = typer.Option(
        None, "--workspace", help="Optional workspace manifest to patch for libraries."
    ),
    execute: bool = typer.Option(False, "-x", "--execute", help="Execute (default is dry-run)."),
    no_remote: bool = typer.Option(False, "--no-remote", help="Keep the new repository local."),
    private: bool = typer.Option(
        False, "--private", help="Create a private GitHub repo (default: public)."
    ),
) -> None:
    """Create a templated Rust crate, with optional GitHub publication and registration."""
    if bin_ == lib:
        raise typer.BadParameter("select exactly one of --bin or --lib")
    _validate(name, dest, bevy_version, workspace if lib else None)
    if registry is not None and not no_remote and not registry.is_file():
        raise typer.BadParameter(f"registry not found: {registry}")
    dry = not execute
    _render_project(name, dest, bevy_version, bin_=bin_, dry=dry)
    if not dry:
        for command in (clippy.cmd, bevy_lint.cmd, test.cmd):
            args = ["-p", name, "--no-tests=pass"] if command is test.cmd else ["-p", name]
            argv, env = command(args)
            run(argv, env_overrides=env or None)
    else:
        log(f"verify {name}: clippy, bevy lint, nextest (--no-tests=pass)", level="dry")
    _bootstrap_in_place(name, dest, create_remote=not no_remote, private=private, dry=dry)
    if registry is not None and not no_remote:
        _register(name, registry, dry=dry)
    if workspace is not None and lib:
        _patch_workspace(name, dest, workspace, dry=dry)
    log(f"initialized {name} at {dest}", level="dry" if dry else "info")
