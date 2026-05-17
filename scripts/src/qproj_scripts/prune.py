"""
Prunes merged worktrees. Fetches and updates main, then removes any branches
which are already merged
"""

from __future__ import annotations

import shlex
from pathlib import Path
from shutil import rmtree

import typer

from qproj_scripts._common import DEFAULT_BRANCH, DEFAULT_REMOTE, VALID_PREFIX, log, run
from qproj_scripts.target import retarget


def main(
    execute: bool = typer.Option(
        False, "-x", "--execute", help="Actually run mutating commands (default is dry-run)."
    ),
) -> None:
    """Prunes already-merged items from the metarepo worktree.
    Runs dry by default. Run with -x to actually execute.
    This MUST be run from the metarepo root.
    """
    dry = not execute

    run(["git", "fetch", "--prune"], dry=dry)

    ff = run(
        shlex.split(f"git -C {DEFAULT_BRANCH} pull {DEFAULT_REMOTE} {DEFAULT_BRANCH} --ff"), dry=dry
    )
    if ff is not None and ff.returncode != 0:
        log("Failed to pull default branch.", level="error")
        raise typer.Exit(code=1)
    retarget("default")

    for dir in [dir for dir in Path.cwd().iterdir() if dir.name in VALID_PREFIX]:
        for branch_path in [branch for branch in dir.iterdir() if branch.is_dir()]:
            # determine if it's been merged
            res = run(
                shlex.split(f"git -C {branch_path} symbolic-ref --short HEAD"), capture_output=True
            )
            if res is None or res.returncode != 0:
                log(f"Could not determine branch name for {branch_path}. Skipping.", level="error")
                continue
            branch = res.stdout.strip()

            res = run(
                shlex.split(
                    f"git merge-base --is-ancestor {branch} {DEFAULT_REMOTE}/{DEFAULT_BRANCH}"
                ),
                capture_output=True,
            )
            merged = res is not None and res.returncode == 0

            res = run(shlex.split(f"git -C {branch} status --porcelain"), capture_output=True)
            clean = res is not None and res.stdout == ""
            if not clean:
                log(f"{branch} is not clean. Skipping.", level="warn")
                continue

            res = run(
                shlex.split(f"git rev-list {branch} ^{DEFAULT_REMOTE}/{branch}"),
                capture_output=True,
            )
            synced = res is not None and res.stdout == ""
            if not synced:
                log(f"{branch} is not synced. Skipping.", level="warn")
                continue

            if merged:
                log(f"Removing {branch}")
                if not dry:
                    rmtree(branch_path)
                run(shlex.split(f"git branch --delete {branch}"), dry=dry)
                run(shlex.split("git worktree prune"), dry=dry)
            else:
                log(f"{branch_path} not yet merged. Skipping.", level="warn")
