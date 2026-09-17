"""Sync the local checkout of each consumer repository.

For each repository listed in ``assets/downstream-repos.json``, ensure an
ordinary Git checkout exists at ``$BASE_DIR/<repo>`` and refresh its remote
refs. Defaults to dry-run; pass ``-x`` / ``--execute`` to mutate.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from importlib.resources import as_file
from pathlib import Path

import typer

from qproj_scripts._common import DEFAULT_BRANCH, DEFAULT_REMOTE, asset, log, run


def write_file(path: Path, content: str, *, dry: bool) -> None:
    level = "dry" if dry else "info"
    log(f"write {path}", level=level)
    if dry:
        return
    path.write_text(content)


def envrc() -> str:
    return (
        'export GH_TOKEN=$(gh auth token 2>/dev/null || echo "")\n'
        "export NIXPKGS_ALLOW_UNFREE=1\n"
        "export LOCAL=1\n"
        "\n"
        "use flake path:infra\n"
    )


def _symlink(target: Path, link: Path, *, dry: bool) -> None:
    level = "dry" if dry else "info"
    log(f"symlink {link} -> {target}", level=level)
    if dry:
        return
    if link.is_symlink() or link.is_file():
        link.unlink()
    elif link.is_dir():
        shutil.rmtree(link)
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target)


def _tracked(repo_dir: Path, path: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo_dir), "ls-files", "--error-unmatch", str(path)],
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def _exclude(repo_dir: Path, path: str, *, dry: bool) -> None:
    exclude = repo_dir / ".git" / "info" / "exclude"
    entry = f"/{path}\n"
    if exclude.is_file() and entry in exclude.read_text():
        return
    log(f"exclude {path} in {repo_dir}", level="dry" if dry else "info")
    if not dry:
        exclude.parent.mkdir(parents=True, exist_ok=True)
        with exclude.open("a") as file:
            file.write(entry)


def _sync_config_links(repo_dir: Path, config_dir: Path, *, dry: bool) -> None:
    """Install untracked local project configuration in an ordinary checkout."""
    for entry in asset(".config").iterdir():
        if entry.name == ".zed":
            for child in entry.iterdir():
                relative = Path(".zed") / child.name
                if not _tracked(repo_dir, relative):
                    _symlink(config_dir / relative, repo_dir / relative, dry=dry)
                    _exclude(repo_dir, str(relative), dry=dry)
        elif not _tracked(repo_dir, Path(entry.name)):
            _symlink(config_dir / entry.name, repo_dir / entry.name, dry=dry)
            _exclude(repo_dir, entry.name, dry=dry)


def _sync_repo(repo: str, base_dir: Path, config_dir: Path, *, dry: bool) -> None:
    repo_dir = base_dir / repo
    typer.echo(f"\n=== {repo} ===")

    if repo_dir.exists():
        if not (repo_dir / ".git").is_dir():
            log(f"{repo_dir} is not an ordinary Git checkout", level="error")
            if not dry:
                raise typer.Exit(code=1)
            return
        log(f"{repo_dir} exists", level="info")
    else:
        run(
            [
                "git",
                "clone",
                "--branch",
                DEFAULT_BRANCH,
                f"https://github.com/{repo}",
                str(repo_dir),
            ],
            dry=dry,
        )

    run(["git", "-C", str(repo_dir), "fetch", DEFAULT_REMOTE, "--prune"], dry=dry)
    _sync_config_links(repo_dir, config_dir, dry=dry)


def main(
    execute: bool = typer.Option(
        False, "-x", "--execute", help="Actually run mutating commands (default is dry-run)."
    ),
) -> None:
    """Sync the local checkout of each workflow consumer repository."""
    home = Path.home()
    base_dir = Path(os.environ.get("BASE_DIR", str(home / "repos")))
    downstream_repos = json.loads(asset("downstream-repos.json").read_text("utf8"))
    dry = not execute

    all_repos: list[str] = [str(repo) for repo in downstream_repos] + ["cubething-qproj/infra"]
    org_dir = base_dir / "cubething-qproj"
    config_dir = org_dir / ".config"
    level = "dry" if dry else "info"

    log("syncing shared config files", "info")
    with as_file(asset(".config")) as src:
        log(f"rm -rf {config_dir}", level)
        if not dry:
            shutil.rmtree(config_dir, ignore_errors=True)
        log(f"cp -r {src} -> {config_dir}", level)
        if not dry:
            shutil.copytree(src, config_dir)

    write_file(org_dir / ".envrc", envrc(), dry=dry)

    for repo in all_repos:
        _sync_repo(repo, base_dir, config_dir, dry=dry)
