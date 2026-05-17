"""Sync the local clone-tree of nanvix/cubething workflow consumer repos.

For each repo listed in the upstream ``consumer-repos.json``,
ensure ``$BASE_DIR/<repo>`` exists with the canonical bare + worktree layout:

Defaults to dry-run; pass ``-x`` / ``--execute`` to actually mutate. Use
``--clobber`` to allow resetting a worktree that has uncommitted changes.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Sequence
from importlib.resources import files
from pathlib import Path
from typing import Literal

import typer

from qproj_scripts import _common

app = typer.Typer(
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def log(msg: str, level: Literal["warn", "miss", "info", "ok"]) -> None:
    prefix = ""
    match level:
        case "warn":
            prefix = "\x1b[33m[warn]"
        case "miss":
            prefix = "\x1b[31m[miss]"
        case "info":
            prefix = "\x1b[34m[info]"
        case "ok":
            prefix = "\x1b[32m[ok]"

    print(f"{prefix}{msg}\x1b[0m", file=sys.stderr, flush=True)


def run(cmd: Sequence[str], *, dry: bool, check: bool = True) -> int:
    _common.echo(list(cmd))
    if dry:
        return 0
    result = subprocess.run(list(cmd), check=check)
    return result.returncode


def write_file(path: Path, content: str, *, dry: bool) -> None:
    _common.echo(["sh", "-c", f"printf %s {content!r} > {path}"])
    if dry:
        return
    path.write_text(content)


def _symlink(target: Path, link: Path, *, dry: bool) -> None:
    """Echo + ``ln -sfT target link`` (no-op in dry-run mode)."""
    _common.echo(["ln", "-sf", "-T", str(target), str(link)])
    if dry:
        return
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(target)


def _copy_best_effort(src: Path, dst: Path, *, dry: bool) -> None:
    """Echo + copy ``src`` to ``dst``; swallow errors (matches ``|| true``)."""
    _common.echo(["cp", str(src), str(dst)])
    if dry:
        return
    try:
        shutil.copyfile(src, dst)
    except OSError as exc:
        log(f"  (copy skipped: {exc})")


def _sync_repo(repo: str, base_dir: Path, config_dir: Path, *, dry: bool, clobber: bool) -> None:
    dir_ = base_dir / repo
    print(f"\n=== {repo} ===", flush=True)

    if dir_.is_dir():
        log(f"{dir_} exists", "ok")
    else:
        log(f"{dir_} missing", "miss")
        run(["mkdir", "-p", str(dir_)], dry=dry)

    bare = dir_ / ".bare"
    if not bare.is_dir():
        log(".bare missing", "miss")
        run(["git", "clone", "--bare", f"https://github.com/{repo}", str(bare)], dry=dry)
    else:
        log(".bare exists", "ok")

    log("syncing .bare", "info")
    run(
        [
            "git",
            "-C",
            str(bare),
            "config",
            "remote.origin.fetch",
            "+refs/heads/*:refs/remotes/origin/*",
        ],
        dry=dry,
    )
    run(["git", "-C", str(bare), "fetch", "--all", "--prune"], dry=dry)
    write_file(dir_ / ".git", "gitdir: ./.bare\n", dry=dry)
    run(["git", "-C", str(bare), "config", "worktree.useRelativePaths", "true"], dry=dry)
    run(["git", "-C", str(bare), "worktree", "repair"], dry=dry)

    log("[info] syncing config files")
    _symlink(config_dir / "AGENTS.md", dir_ / "AGENTS.md", dry=dry)
    _symlink(config_dir / "justfile", dir_ / "justfile", dry=dry)
    _copy_best_effort(config_dir / "pyrightconfig.json", dir_ / "pyrightconfig.json", dry=dry)

    default_branch = _default_branch(repo)
    write_file(dir_ / ".default-branch", f"{default_branch}\n", dry=dry)

    log("[info] syncing default branch")
    wt = dir_ / default_branch
    if not wt.is_dir():
        log(f"[miss] {wt} missing")
        run(["git", "-C", str(bare), "worktree", "add", str(wt), default_branch], dry=dry)
    else:
        log(f"[ok] {wt} exists")

    status = subprocess.run(
        ["git", "-C", str(wt), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    if status:
        if clobber:
            log(f"[warn] {wt} has uncommitted changes. Clobbering...")
        else:
            log(f"[warn] {wt} has uncommitted changes. Re-run with --clobber to overwrite.")
            if not dry:
                raise typer.Exit(code=1)
    else:
        log(f"[ok] {wt} clean")

    run(["git", "-C", str(wt), "reset", "--hard", f"origin/{default_branch}"], dry=dry)
    run(["git", "-C", str(wt), "clean", "-fd"], dry=dry)


@app.callback(invoke_without_command=True)
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
    downstream_repos = (
        files("qproj_scripts").joinpath("assets/downstream-repos.json").read_text("utf8")
    )
    downstream_repos = json.loads(downstream_repos)
    dry = not execute

    all_repos: list[str] = [str(r) for r in downstream_repos] + ["cubething-qproj/infra"]

    for repo in all_repos:
        _sync_repo(repo, base_dir, config_dir, dry=dry, clobber=clobber)
