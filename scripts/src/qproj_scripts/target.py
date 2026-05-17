"""Repoint the ``active`` symlink at a sibling worktree directory.

Replaces ``./active`` with a symlink to ``<dir>`` (or ``$DEFAULT_BRANCH``
when ``dir`` is the literal string ``default``), then prints the
resulting symlink for confirmation.
"""

from __future__ import annotations

import os
from pathlib import Path

import typer

from qproj_scripts import _common


def main(
    dir_: str = typer.Argument(..., metavar="DIR", help="Worktree dir, or 'default'."),
) -> None:
    """Repoint ``./active`` at ``DIR`` (or ``$DEFAULT_BRANCH`` for ``default``)."""
    target = dir_
    if target == "default":
        target = os.environ.get("DEFAULT_BRANCH", "main")

    if not Path(target).is_dir():
        typer.echo(f"Directory {target} does not exist", err=True)
        raise typer.Exit(code=1)

    _common.run(["ln", "-s", target, "-T", "active", "-f"])
    _common.run(["ls", "active", "-l"])
