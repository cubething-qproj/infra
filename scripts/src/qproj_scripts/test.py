"""Run the workspace test suite via ``cargo nextest run``.

With no arguments, selects the whole workspace. Otherwise all arguments are
forwarded after the ``run`` subcommand so feature and package-selection flags
work naturally.
"""

from __future__ import annotations

import typer

from qproj_scripts import _common


def cmd(extra: list[str]) -> tuple[list[str], dict[str, str]]:
    """Return the standard nextest invocation and environment."""
    selection = extra if extra else ["--workspace"]
    return ["cargo", "nextest", "run", *selection], {"RUSTC_WRAPPER": "sccache"}


def main(ctx: typer.Context) -> None:
    """Run ``cargo nextest run``, forwarding feature and selection arguments."""
    argv, env = cmd(_common.command_args(ctx.args))
    result = _common.run(argv, check=False, env_overrides=env)
    raise typer.Exit(result.returncode)  # pyright: ignore[reportOptionalMemberAccess]
