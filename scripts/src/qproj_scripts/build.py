"""Build the workspace.

Thin wrapper over ``cargo build``. All extra arguments are forwarded.
Pins ``RUSTC_WRAPPER=sccache`` for shared incremental cache hits.
"""

from __future__ import annotations

import typer

from qproj_scripts import _common


def cmd(extra: list[str]) -> tuple[list[str], dict[str, str]]:
    """Return the ``(argv, env_overrides)`` for the standard build invocation.

    Exposed so sibling verbs (e.g. :mod:`qproj_scripts.play`) can run the
    same build in-process.
    """
    return ["cargo", "build", *extra], {"RUSTC_WRAPPER": "sccache"}


def main(ctx: typer.Context) -> None:
    """Run ``cargo build`` with any forwarded arguments."""
    argv, env = cmd(ctx.args)
    result = _common.run(argv, env_overrides=env, check=False)
    raise typer.Exit(result.returncode)
