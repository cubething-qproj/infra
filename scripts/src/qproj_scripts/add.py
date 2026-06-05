"""Create a new git worktree branched off ``$DEFAULT_REMOTE/$DEFAULT_BRANCH`` (origin/main).

Validates that the requested branch name uses one of the canonical
prefixes (``fix/``, ``feat/``, ``doc/``, ``tests/``, ``release/``),
fetches from the remote, then runs ``git worktree add`` with a fresh
branch based on ``<DEFAULT_REMOTE>/<DEFAULT_BRANCH>``.

When ``-t/--target`` is passed, the new branch is also checked out in
``./active/`` (via :mod:`qproj_scripts.target`) so subsequent
``cd active && ...`` invocations operate on it.
"""

from __future__ import annotations

import typer

from qproj_scripts import target as target_mod
from qproj_scripts._common import DEFAULT_BRANCH, DEFAULT_REMOTE, PREFIX_RE, log, run


def main(
    name: str = typer.Argument(..., help="Branch/worktree name, e.g. feat/foo."),
    target: bool = typer.Option(
        False,
        "-t",
        "--target",
        help="After creating the worktree, also check out NAME in active/.",
    ),
    clobber: bool = typer.Option(
        False,
        "--clobber",
        help="With -t, force the active/ checkout even if it has uncommitted changes.",
    ),
) -> None:
    """Create a worktree on a new branch ``NAME``
    off ``$DEFAULT_ORIGIN/$DEFAULT_BRANCH`` (origin/main)."""
    if not PREFIX_RE.match(name):
        log(f"Invalid branch name: {name}", level="error")
        log("Valid branch names are: fix/*, feat/*, doc/*, tests/*, release/*", level="error")
        raise typer.Exit(code=1)

    run(["git", "fetch"])
    run(
        [
            "git",
            "worktree",
            "add",
            name,
            "-b",
            name,
            f"{DEFAULT_REMOTE}/{DEFAULT_BRANCH}",
        ],
    )

    if target:
        target_mod.retarget(name, clobber=clobber)
