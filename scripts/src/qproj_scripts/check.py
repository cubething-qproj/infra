"""Run Clippy and ``bevy_lint`` concurrently.

Both linters use isolated target dirs (``target/clippy`` and
``target/bevy_lint``) so they can build in parallel without contention.
Exits non-zero if either linter fails.

Multiple packages may be named; they are forwarded as repeated ``-p PKG``
pairs to both linters (matching cargo's own ``-p`` semantics). With no
packages, both linters run once over the whole workspace.

When ``LOCAL=1`` is set, each named package instead spawns its own pair of
clippy + bevy_lint invocations with ``--manifest-dir=<pkg>/active``,
running all of them concurrently. (Preserved as-is from the pre-refactor
script; cargo does not natively accept ``--manifest-dir``.)
"""

from __future__ import annotations

import os
import subprocess

import typer

from qproj_scripts import _common, bevy_lint, clippy


def _spawn(argv: list[str], env_overrides: dict[str, str]) -> subprocess.Popen[bytes]:
    """Echo ``argv`` and ``Popen`` it with ``env_overrides`` layered on os.environ."""
    _common.log(" ".join(argv), None)
    env = {**os.environ, **env_overrides} if env_overrides else None
    return subprocess.Popen(argv, env=env)


def main(
    packages: list[str] | None = typer.Argument(
        None,
        metavar="[PACKAGE...]",
        help="Cargo packages to scope both linters to. Repeatable; forwarded as -p PKG pairs.",
    ),
) -> None:
    """Run Clippy and bevy_lint in parallel; non-zero if either fails."""
    pkgs = packages or []

    invocations: list[tuple[list[str], dict[str, str]]] = []
    if os.environ.get("LOCAL") == "1" and pkgs:
        for pkg in pkgs:
            manifest_arg = f"--manifest-dir={pkg}/active"
            invocations.append(clippy.cmd([manifest_arg]))
            invocations.append(bevy_lint.cmd([manifest_arg]))
    else:
        pkg_args: list[str] = []
        for pkg in pkgs:
            pkg_args.extend(["-p", pkg])
        invocations.append(clippy.cmd(pkg_args))
        invocations.append(bevy_lint.cmd(pkg_args))

    procs = [_spawn(argv, env) for argv, env in invocations]
    rcs = [p.wait() for p in procs]
    raise typer.Exit(max(rcs) if any(rcs) else 0)
