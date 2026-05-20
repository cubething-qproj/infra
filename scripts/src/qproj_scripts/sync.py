"""Sync the local clone-tree of consumer repos.

For each repo listed in ``assets/downstream-repos.json``,
ensure ``$BASE_DIR/<repo>`` exists with the canonical bare + worktree layout:

Defaults to dry-run; pass ``-x`` / ``--execute`` to actually mutate. Use
``--clobber`` to allow resetting a worktree that has uncommitted changes.
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
    # GPU driver wrapping is handled per-invocation by `just play`
    # (which prepends `nix run github:nix-community/nixGL#$NIXGL`), so
    # the devshell itself is pure -- no `--impure`, no per-GPU variant.
    # Override the wrapper for a host by exporting `NIXGL` in .env.local.
    return (
        'export GH_TOKEN=$(gh auth token 2>/dev/null || echo "")\n'
        "export NIXPKGS_ALLOW_UNFREE=1\n"
        "export LOCAL=1\n"
        "\n"
        "use flake path:infra/$(readlink infra/active)\n"
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
    link.symlink_to(target)


def _sync_repo(repo: str, base_dir: Path, config_dir: Path, *, dry: bool, clobber: bool) -> None:
    repo_dir = base_dir / repo
    typer.echo(f"\n=== {repo} ===")

    if repo_dir.is_dir():
        log(f"{repo_dir} exists", "info")
    else:
        log(f"creating {repo_dir}", "dry" if dry else "info")
        if not dry:
            repo_dir.mkdir(parents=True, exist_ok=True)

    log("syncing .bare", "info")
    bare = repo_dir / ".bare"
    if not bare.is_dir():
        run(["git", "clone", "--bare", f"https://github.com/{repo}", str(bare)], dry=dry)
    else:
        log(".bare exists", "info")

    run(
        [
            "git",
            "-C",
            str(bare),
            "config",
            f"remote.{DEFAULT_REMOTE}.fetch",
            f"+refs/heads/*:refs/remotes/{DEFAULT_REMOTE}/*",
        ],
        dry=dry,
    )

    write_file(repo_dir / ".git", "gitdir: ./.bare\n", dry=dry)
    run(["git", "-C", str(bare), "fetch", "--all", "--prune"], dry=dry)
    run(["git", "-C", str(bare), "config", "worktree.useRelativePaths", "true"], dry=dry)
    run(["git", "-C", str(bare), "worktree", "repair"], dry=dry)

    log(f"syncing {DEFAULT_BRANCH}", "info")
    wt = repo_dir / DEFAULT_BRANCH
    if not wt.is_dir():
        log(f"{wt} missing", "info")
        run(["git", "-C", str(bare), "worktree", "add", str(wt), DEFAULT_BRANCH], dry=dry)
    else:
        log(f"{wt} exists", "info")

    status = ""
    if not dry:
        status = subprocess.run(
            ["git", "-C", str(wt), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
    if status:
        if clobber:
            log(f"{wt} has uncommitted changes. Clobbering...", "warn")
        else:
            log(f"{wt} has uncommitted changes. Re-run with --clobber to overwrite.", "error")
            if not dry:
                raise typer.Exit(code=1)
    else:
        log(f"{wt} clean", "info")

    run(["git", "-C", str(wt), "reset", "--hard", f"{DEFAULT_REMOTE}/{DEFAULT_BRANCH}"], dry=dry)
    run(["git", "-C", str(wt), "clean", "-fd"], dry=dry)

    log("Symlinking config files", "info")
    for asset_ in asset(".config").iterdir():
        _symlink(config_dir / asset_.name, repo_dir / asset_.name, dry=dry)


def main(
    execute: bool = typer.Option(
        False, "-x", "--execute", help="Actually run mutating commands (default is dry-run)."
    ),
    clobber: bool = typer.Option(
        False, "--clobber", help="Hard-reset worktrees even with uncommitted changes."
    ),
) -> None:
    """Sync the local clone-tree of workflow consumer repos."""
    home = Path.home()
    base_dir = Path(os.environ.get("BASE_DIR", str(home / "repos")))
    downstream_repos = asset("downstream-repos.json").read_text("utf8")
    downstream_repos = json.loads(downstream_repos)
    dry = not execute

    all_repos: list[str] = [str(r) for r in downstream_repos] + ["cubething-qproj/infra"]

    log("syncing shared config files", "info")
    org_dir = base_dir / "cubething-qproj"
    config_dir = org_dir / ".config"

    level = "dry" if dry else "info"
    with as_file(asset(".config")) as src:
        log(f"rm -rf {config_dir}", level)
        if not dry:
            shutil.rmtree(config_dir, ignore_errors=True)
        log(f"cp -r {src} -> {config_dir}", level)
        if not dry:
            shutil.copytree(src, config_dir)

    log("writing .envrc", "info")
    envrc_content = envrc()
    write_file(org_dir / ".envrc", envrc_content, dry=dry)

    for repo in all_repos:
        _sync_repo(repo, base_dir, config_dir, dry=dry, clobber=clobber)
