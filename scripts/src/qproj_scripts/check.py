"""Run Clippy and ``bevy_lint`` using local or CI execution policy.

Locally the linters run concurrently with isolated target directories. In CI
they run sequentially and share Cargo's default ``target`` directory with
builds and tests, reducing peak disk usage.

Arguments are forwarded unchanged to both linters. For backward compatibility,
a list containing only positional values is treated as package shorthand and
expanded to repeated ``-p PKG`` pairs. With ``LOCAL=1``, that shorthand keeps
the existing per-package ``--manifest-dir=<pkg>`` fan-out.
"""

from __future__ import annotations

import os
import subprocess

import typer

from qproj_scripts import _common, bevy_lint, clippy
from qproj_scripts._common import ExitCode, Invocation


def _spawn(invocation: Invocation) -> subprocess.Popen[bytes]:
    """Echo and spawn an invocation with its overrides layered on ``os.environ``."""
    _common.log(" ".join(invocation.argv), None)
    env = {**os.environ, **invocation.env_overrides} if invocation.env_overrides else None
    return subprocess.Popen(invocation.argv, env=env)


def _invocations(extra: list[str]) -> list[Invocation]:
    """Construct linter invocations while retaining positional package shorthand."""
    return [
        Invocation.from_command(clippy.cmd(extra)),
        Invocation.from_command(bevy_lint.cmd(extra)),
    ]


def _run_sequential(invocations: list[Invocation]) -> list[ExitCode]:
    """Run each invocation to completion in order and return its exit code."""
    return [
        _common.run(
            invocation.argv,
            env_overrides=invocation.env_overrides or None,
            check=False,
        ).returncode  # pyright: ignore[reportOptionalMemberAccess]
        for invocation in invocations
    ]


def main(ctx: typer.Context) -> None:
    """Run both linters; sequentially in CI and concurrently otherwise."""
    invocations = [
        Invocation.from_command(clippy.cmd(ctx.args)),
        Invocation.from_command(bevy_lint.cmd(ctx.args)),
    ]
    if _common.is_ci():
        rcs = _run_sequential(invocations)
    else:
        procs = [_spawn(invocation) for invocation in invocations]
        rcs = [proc.wait() for proc in procs]
    raise typer.Exit(max(rcs) if any(rcs) else 0)
