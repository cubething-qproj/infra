"""Run Clippy with the workspace's standard target-directory policy.

Local runs set ``CARGO_TARGET_DIR`` to the organization-level ``target/clippy``
so Clippy can run alongside ``bevy_lint``. CI uses Cargo's default target directory
to minimize peak disk usage.
"""

from __future__ import annotations

import typer

from qproj_scripts import _common


def cmd(extra: list[str]) -> tuple[list[str], dict[str, str]]:
    """Return the ``(argv, env_overrides)`` for the standard Clippy invocation.

    Exposed so :mod:`qproj_scripts.check` can launch Clippy in parallel with
    ``bevy_lint`` without re-entering a Python interpreter.
    """
    env = (
        {}
        if _common.is_ci()
        else {"CARGO_TARGET_DIR": str(_common.organization_dir() / "target" / "clippy")}
    )
    return ["cargo", "clippy", *extra], env


def main(ctx: typer.Context) -> None:
    """Run Clippy, forwarding all arguments to Cargo unchanged."""
    argv, env = cmd(ctx.args)
    result = _common.run(argv, env_overrides=env or None, check=False)
    raise typer.Exit(result.returncode)  # pyright: ignore[reportOptionalMemberAccess]
