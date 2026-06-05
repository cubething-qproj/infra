"""Create a new git worktree branched off ``$DEFAULT_REMOTE/$DEFAULT_BRANCH``.

Without ``-t``: creates a dedicated worktree at ``./NAME/`` on a fresh
branch ``NAME`` based on ``origin/main``.

With ``-t/--target``: instead of a dedicated per-branch worktree,
creates the branch directly in ``./active/`` via
:func:`qproj_scripts.target.retarget`. Use this for ephemeral work
where a separate worktree dir would be noise; git won't let the same
branch be checked out in two worktrees anyway.
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
        help="Create the branch in active/ instead of a dedicated worktree dir.",
    ),
    clobber: bool = typer.Option(
        False,
        "--clobber",
        help="With -t, force the active/ checkout even if it has uncommitted changes.",
    ),
) -> None:
    """Create a worktree on a new branch ``NAME`` off ``origin/$DEFAULT_BRANCH``."""
    if not PREFIX_RE.match(name):
        log(f"Invalid branch name: {name}", level="error")
        log("Valid branch names are: fix/*, feat/*, doc/*, tests/*, release/*", level="error")
        raise typer.Exit(code=1)

    if target:
        # retarget() handles the fetch + checkout-with-prefix-check;
        # since NAME doesn't exist yet, it takes the create-from-origin
        # path inside active/.
        target_mod.retarget(name, clobber=clobber)
        return

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
