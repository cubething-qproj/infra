from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Literal

import typer

DEFAULT_BRANCH = os.environ.get("DEFAULT_BRANCH", "main")
DEFAULT_REMOTE = os.environ.get("DEFAULT_REMOTE", "origin")


type ExitCode = int


@dataclass(frozen=True, slots=True)
class Invocation:
    """One external command and its environment overrides."""

    argv: list[str]
    env_overrides: dict[str, str]

    @classmethod
    def from_command(cls, command: tuple[list[str], dict[str, str]]) -> Invocation:
        return cls(*command)


def is_ci() -> bool:
    """Return whether the process is running in CI.

    GitHub Actions exports ``CI=true``. Treat any non-empty value as enabled so
    local callers can exercise the same behavior with ``CI=1``.
    """
    return bool(os.environ.get("CI"))


def command_args(explicit: Sequence[str]) -> list[str]:
    """Combine explicit arguments with a safely encoded CI argument array.

    The reusable workflow sets ``QPROJ_COMMAND_ARGS_JSON`` for one command
    step at a time. Parsing it here avoids interpolating caller-controlled text
    into a shell command.
    """
    raw = os.environ.get("QPROJ_COMMAND_ARGS_JSON")
    if raw is None:
        return list(explicit)
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as error:
        raise typer.BadParameter("QPROJ_COMMAND_ARGS_JSON must be valid JSON") from error
    if not isinstance(decoded, list) or not all(isinstance(arg, str) for arg in decoded):
        raise typer.BadParameter("QPROJ_COMMAND_ARGS_JSON must be a JSON array of strings")
    return [*decoded, *explicit]


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
