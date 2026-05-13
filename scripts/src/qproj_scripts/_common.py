"""Shared stdlib-only helpers for the qproj_scripts verb modules.

Provides:

- :func:`run` / :func:`echo` — subprocess wrapper that prints a shell-quoted
  preview of the command (``set -x`` style) before running it, with
  optional environment overrides layered on ``os.environ``.
- :func:`scripts_dir` / :func:`infra_main_dir` — path helpers so verb
  modules can locate sibling resources without depending on cwd.
- :func:`rustc_sysroot` — cached lookup of the active toolchain sysroot.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path


def scripts_dir() -> Path:
    """Return ``infra/main/scripts`` (the package's grandparent directory)."""
    # __file__ = .../infra/main/scripts/src/qproj_scripts/_common.py
    return Path(__file__).resolve().parent.parent.parent


def infra_main_dir() -> Path:
    """Return ``infra/main`` (parent of :func:`scripts_dir`)."""
    return scripts_dir().parent


def echo(cmd: list[str], *, env_overrides: dict[str, str] | None = None) -> None:
    """Print a shell-quoted preview of ``cmd`` to stderr (``set -x`` style)."""
    prefix = ""
    if env_overrides:
        prefix = " ".join(f"{k}={shlex.quote(v)}" for k, v in env_overrides.items()) + " "
    print(f"+ {prefix}{shlex.join(cmd)}", file=sys.stderr, flush=True)


def run(
    cmd: list[str],
    *,
    env_overrides: dict[str, str] | None = None,
    check: bool = True,
    **kwargs: object,
) -> subprocess.CompletedProcess[str]:
    """Run ``cmd`` after echoing it. ``env_overrides`` is layered on ``os.environ``."""
    echo(cmd, env_overrides=env_overrides)
    env = None
    if env_overrides is not None:
        env = {**os.environ, **env_overrides}
    return subprocess.run(cmd, check=check, env=env, **kwargs)  # pyright: ignore[reportCallIssue, reportArgumentType]


def rustc_sysroot() -> str:
    """Return ``rustc --print sysroot`` (stripped)."""
    out = subprocess.run(
        ["rustc", "--print", "sysroot"], capture_output=True, text=True, check=True
    )
    return out.stdout.strip()
