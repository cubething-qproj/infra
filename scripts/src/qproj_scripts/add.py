"""Create a new git worktree branched off ``origin/$DEFAULT_BRANCH``.

This is the Python implementation of the ``just add`` recipe: it
validates that the requested branch name uses one of the canonical
prefixes (``fix/``, ``feat/``, ``doc/``, ``tests/``, ``release/``),
fetches from the remote, then runs ``git worktree add`` with a fresh
branch based on ``origin/<DEFAULT_BRANCH>``.
"""

from __future__ import annotations

import os
import re

import typer

from qproj_scripts import _common

app = typer.Typer(
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)

_VALID_PREFIX = re.compile(r"^(fix|feat|doc|tests|release)/")


@app.callback(invoke_without_command=True)
def main(
    name: str = typer.Argument(..., help="Branch/worktree name, e.g. feat/foo."),
) -> None:
    """Create a worktree on a new branch ``NAME`` off ``origin/$DEFAULT_BRANCH``."""
    if not _VALID_PREFIX.match(name):
        typer.echo(f"Invalid branch name: {name}", err=True)
        typer.echo(
            "Valid branch names are: fix/*, feat/*, doc/*, tests/*, release/*",
            err=True,
        )
        raise typer.Exit(code=1)

    default_branch = os.environ.get("DEFAULT_BRANCH", "main")

    _common.run(["git", "fetch"])
    _common.run(
        ["git", "worktree", "add", name, "-b", name, f"origin/{default_branch}"],
    )
