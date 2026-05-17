"""Create a new git worktree branched off ``$DEFAULT_REMOTE/$DEFAULT_BRANCH`` (origin/main).

Validates that the requested branch name uses one of the canonical
prefixes (``fix/``, ``feat/``, ``doc/``, ``tests/``, ``release/``),
fetches from the remote, then runs ``git worktree add`` with a fresh
branch based on ``<DEFAULT_REMOTE>/<DEFAULT_BRANCH>``.
"""

from __future__ import annotations

import typer

from qproj_scripts import _common


def main(
    name: str = typer.Argument(..., help="Branch/worktree name, e.g. feat/foo."),
) -> None:
    """Create a worktree on a new branch ``NAME``
    off ``$DEFAULT_ORIGIN/$DEFAULT_BRANCH`` (origin/main)."""
    if not _common.PREFIX_RE.match(name):
        typer.echo(f"Invalid branch name: {name}", err=True)
        typer.echo(
            "Valid branch names are: fix/*, feat/*, doc/*, tests/*, release/*",
            err=True,
        )
        raise typer.Exit(code=1)

    _common.run(["git", "fetch"])
    _common.run(
        [
            "git",
            "worktree",
            "add",
            name,
            "-b",
            name,
            f"{_common.DEFAULT_REMOTE}/{_common.DEFAULT_BRANCH}",
        ],
    )
