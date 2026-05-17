from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Sequence
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Literal

import typer

DEFAULT_BRANCH = os.environ.get("DEFAULT_BRANCH", "main")
DEFAULT_REMOTE = os.environ.get("DEFAULT_REMOTE", "origin")
VALID_PREFIX = ["fix", "feat", "doc", "tests", "release"]
PREFIX_RE = re.compile(rf"^({'|'.join(VALID_PREFIX)})/")


def asset(path: str | Path) -> Traversable:
    return files("qproj_scripts").joinpath(Path("assets") / path)


def log(msg: str, level: Literal["warn", "error", "info", "dry"] | None = None) -> None:
    prefix = ""
    match level:
        case "warn":
            prefix = "\x1b[33m[warn] "
        case "error":
            prefix = "\x1b[31m[error] "
        case "info":
            prefix = "\x1b[34m[info] "
        case "dry":
            prefix = "\x1b[38;5;245m[dry] "

    typer.echo(f"{prefix}{msg}\x1b[0m", file=sys.stderr)


def run(
    cmd: Sequence[str],
    *,
    check: bool = True,
    dry: bool = False,
    env_overrides: dict[str, str] | None = None,
    **kwargs,
) -> subprocess.CompletedProcess[str] | None:
    level = "dry" if dry else "info"
    log(" ".join(cmd), level=level)
    if dry:
        return None
    env = None
    if env_overrides is not None:
        env = {**os.environ, **env_overrides}
    return subprocess.run(list(cmd), check=check, env=env, text=True, **kwargs)  # pyright: ignore[reportCallIssue]


def scripts_dir() -> Path:
    """Return ``infra/main/scripts`` (the package's grandparent directory)."""
    # __file__ = .../infra/main/scripts/src/qproj_scripts/_common.py
    return Path(__file__).resolve().parent.parent.parent


def infra_main_dir() -> Path:
    """Return ``infra/main`` (parent of :func:`scripts_dir`)."""
    return scripts_dir().parent


def rustc_sysroot() -> str:
    """Return ``rustc --print sysroot`` (stripped)."""
    out = subprocess.run(
        ["rustc", "--print", "sysroot"], capture_output=True, text=True, check=True
    )
    return out.stdout.strip()
