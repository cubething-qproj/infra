"""Run ``bevy lint`` with the right sysroot and isolated target dir.

Invokes the ``lint`` subcommand of the ``bevy`` CLI (provided by the upstream
bevy_cli flake), which dispatches to ``bevy_lint_driver``.

Sets ``RUSTC_WRAPPER=`` (disables sccache, which conflicts with bevy_lint's
custom driver) and ``BEVY_LINT_SYSROOT`` to the active toolchain's sysroot.
"""

from __future__ import annotations

import typer

from qproj_scripts import _common


def cmd(extra: list[str]) -> tuple[list[str], dict[str, str]]:
    """Return the ``(argv, env_overrides)`` for the standard ``bevy lint`` invocation.

    Exposed so :mod:`qproj_scripts.check` can launch ``bevy_lint`` in parallel
    with Clippy without re-entering a Python interpreter.
    """
    argv = [
        "bevy",
        "lint",
        "--config",
        'profile.dev.codegen-backend="llvm"',
        "--all-features",
        "--target-dir=target/bevy_lint",
        *extra,
    ]
    env = {
        "RUSTC_WRAPPER": "",
        "BEVY_LINT_SYSROOT": _common.rustc_sysroot(),
    }
    return argv, env


def main(ctx: typer.Context) -> None:
    """Run ``bevy lint --all-features --target-dir=target/bevy_lint``."""
    argv, env = cmd(ctx.args)
    result = _common.run(argv, env_overrides=env, check=False)
    raise typer.Exit(result.returncode)  # pyright: ignore[reportOptionalMemberAccess]
