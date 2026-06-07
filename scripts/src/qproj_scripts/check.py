"""Run Clippy across the workspace or a list of packages.

Multiple packages are forwarded as repeated ``-p PKG`` pairs (matching
cargo's own ``-p`` semantics). With no packages, runs once over the whole
workspace.

When ``LOCAL=1`` is set, each named package instead spawns its own clippy
invocation with ``--manifest-dir=<pkg>/active``, running them
concurrently. (Cargo does not natively accept ``--manifest-dir``.)
"""

from __future__ import annotations

import os
import subprocess

import typer

from qproj_scripts import _common, clippy


def _spawn(argv: list[str], env_overrides: dict[str, str]) -> subprocess.Popen[bytes]:
    _common.log(" ".join(argv), None)
    env = {**os.environ, **env_overrides} if env_overrides else None
    return subprocess.Popen(argv, env=env)


def main(
    packages: list[str] | None = typer.Argument(
        None,
        metavar="[PACKAGE...]",
        help="Cargo packages to scope to. Repeatable; forwarded as -p PKG pairs.",
    ),
) -> None:
    """Run Clippy; non-zero if any invocation fails."""
    pkgs = packages or []

    invocations: list[tuple[list[str], dict[str, str]]] = []
    if os.environ.get("LOCAL") == "1" and pkgs:
        for pkg in pkgs:
            invocations.append(clippy.cmd([f"--manifest-dir={pkg}/active"]))
    else:
        pkg_args: list[str] = []
        for pkg in pkgs:
            pkg_args.extend(["-p", pkg])
        invocations.append(clippy.cmd(pkg_args))

    procs = [_spawn(argv, env) for argv, env in invocations]
    rcs = [p.wait() for p in procs]
    raise typer.Exit(max(rcs) if any(rcs) else 0)
