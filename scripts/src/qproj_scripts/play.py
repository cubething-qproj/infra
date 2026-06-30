"""Build a Cargo binary and either exec it locally or relay it to a psync host.

Two modes, chosen by ``--mode`` (default ``auto``):

``local``
    Re-adds ``target/debug/deps`` to ``LD_LIBRARY_PATH`` (so dylib-feature
    builds resolve ``libbevy_dylib-<hash>.so`` under nix-shell) and injects
    ``CARGO_MANIFEST_DIR=$PWD`` into the child env so Bevy's ``AssetPlugin``
    finds the crate's ``assets/`` at runtime, then ``os.execvpe``'s the
    binary. GPU driver wrapping (nixGL) is the caller's responsibility.

``remote``
    ``patchelf``-rewrites the binary to load through the host's standard
    loader + a ``/home/psync/lib`` RPATH, rsyncs libstd and libbevy_dylib to
    ``$PSYNC_SERVER_IP``, and hands the binary off to ``cubething_psync``
    via ``uvx``. Picked automatically when both ``SSH_CLIENT`` and
    ``PSYNC_SERVER_IP`` are set.

``-A``/``--assets`` and ``-e``/``--env`` are psync-only knobs: they are
forwarded to ``psync`` in remote mode and warn-and-ignored in local mode.
We do NOT set ``BEVY_ASSET_ROOT``; Bevy locates ``assets/`` via the
``CARGO_MANIFEST_DIR`` we inject locally, and psync handles the asset
relay itself in remote mode.

Tokens after a literal ``--`` are forwarded verbatim to the binary's argv
(or merged into psync's ``-a`` payload). The legacy ``-a``/``--args`` flag
still works with a deprecation warning.

``--dry-run`` prints the resolved plan and exits. ``--skip-build`` keeps
everything else intact but skips the ``cargo build`` invocation for fast
runtime iteration. ``_common.run`` already echoes every shell-out at info
level before running it, so build/patchelf/rsync/psync invocations are
visible by default; no extra verbosity flag is needed.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import typer

from qproj_scripts import _common, build

# ---------------------------------------------------------------------------
# Run plan
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RunPlan:
    """Fully-resolved description of one ``play`` invocation.

    Captures everything both the local exec path and the remote psync
    relay need to know, so dispatch reduces to picking an executor.
    """

    target_path: Path
    build_argv: list[str]
    build_env: dict[str, str]
    # User-supplied ``-A`` value, verbatim. Only consulted by the local
    # executor to warn that the flag is psync-only (``-A`` is silently
    # ignored in local mode otherwise).
    assets_explicit: Path | None
    # ``assets_explicit`` falling back to ``cwd/assets`` when that exists.
    # Only the remote executor reads this, to forward ``-A`` to psync.
    assets_autodetected: Path | None
    env_vars: str
    cmd_args: str
    # Tokens supplied after a literal ``--`` on the command line, forwarded
    # verbatim to the binary's argv. The modern replacement for ``-a``.
    passthrough: tuple[str, ...]
    mode: Literal["local", "remote"]
    dry_run: bool = False
    skip_build: bool = False


# ---------------------------------------------------------------------------
# Remote (SSH / psync) mode helpers
# ---------------------------------------------------------------------------


_LIBSTD_RE = re.compile(r"libstd-[0-9A-Za-z]+\.so")
_LIBSTD_RE_NO_HASH = re.compile(r"libstd\.so")
_LIBBEVY_RE = re.compile(r"libbevy_dylib-[0-9A-Za-z]+\.so")
_LIBBEVY_RE_NO_HASH = re.compile(r"libbevy_dylib\.so")


def _patch_elf_for_psync(target: Path) -> None:
    """patchelf the binary + rsync its dynamic deps to the psync server."""
    elfdata = subprocess.run(
        ["readelf", "-d", str(target)], capture_output=True, text=True, check=True
    ).stdout

    dylib_path = Path("./target/debug/libbevy_dylib.so")
    sysroot = Path(_common.rustc_sysroot())

    libstd_match = _LIBSTD_RE.search(elfdata)
    if not libstd_match:
        libstd_match = _LIBSTD_RE_NO_HASH.search(elfdata)
        if libstd_match is None:
            raise typer.BadParameter("Could not find libstd NEEDED entry in the binary")
    libstd = libstd_match.group(0)

    stdlib_candidates = list(sysroot.rglob(libstd))
    if not stdlib_candidates:
        raise typer.BadParameter(f"could not locate {libstd} under {sysroot}")
    stdlib_path = stdlib_candidates[0]

    libbevy_match = _LIBBEVY_RE.search(elfdata)
    if not libbevy_match:
        libbevy_match = _LIBBEVY_RE_NO_HASH.search(elfdata)
        if libbevy_match is None:
            raise typer.BadParameter("Could not find libbevy_dylib NEEDED entry in the binary")
    else:
        libbevy = libbevy_match.group(0)
        _common.run(["patchelf", "--replace-needed", libbevy, "libbevy_dylib.so", str(target)])

    psync_ip = os.environ.get("PSYNC_SERVER_IP")
    if not psync_ip:
        raise typer.BadParameter("PSYNC_SERVER_IP not set; required in SSH mode")

    _common.run(["patchelf", "--set-interpreter", "/lib64/ld-linux-x86-64.so.2", str(target)])
    _common.run(["patchelf", "--set-rpath", "/home/psync/lib", str(target)])
    # sync dependencies - NOT the project itself
    _common.run(
        [
            "rsync",
            "-avzr",
            "-e",
            "/usr/bin/ssh -l psync -p 5022",
            "-L",
            "--progress",
            "--mkpath",
            str(dylib_path),
            str(stdlib_path),
            f"{psync_ip}:/home/psync/lib",
        ]
    )


def _default_package_name() -> str:
    """Return ``[package].name`` from the cwd's ``Cargo.toml``."""
    cargo_toml = Path("Cargo.toml")
    if not cargo_toml.exists():
        raise typer.BadParameter(
            "no Cargo.toml in cwd; pass an explicit binary path or run from a crate root"
        )
    with cargo_toml.open("rb") as f:
        manifest = tomllib.load(f)
    try:
        return manifest["package"]["name"]
    except KeyError as e:
        raise typer.BadParameter(
            "Cargo.toml has no [package].name (virtual workspace?); pass -p PACKAGE "
            "or an explicit binary path"
        ) from e


# ---------------------------------------------------------------------------
# Main command
# ---------------------------------------------------------------------------


_VALID_MODES = frozenset({"auto", "local", "remote"})

_DEPRECATED_ARGS_MSG = "--args/-a is deprecated; use '-- <args>' passthrough instead"


def build_plan(
    *,
    example: str | None,
    package: str | None,
    build_args: str,
    env_vars: str,
    cmd_args: str,
    assets: Path | None,
    extras: list[str],
    environ: Mapping[str, str],
    mode: str = "auto",
    passthrough: Sequence[str] = (),
    dry_run: bool = False,
    skip_build: bool = False,
) -> RunPlan:
    """Resolve CLI arguments into a fully-determined :class:`RunPlan`.

    Pure modulo :func:`build.cmd` (which is itself a pure argv-builder).
    Both execution paths consume the returned plan; no caller-side
    interpretation of the raw flags should remain.
    """
    file_set = False
    file_path: Path | None = None
    if extras:
        # First positional extra is treated as the explicit binary path.
        file_path = Path(extras[0])
        file_set = True

    cargo_example = ["--example", example] if example else []
    cargo_package: list[str] = []
    if package:
        cargo_package = ["-p", package]
        if not file_set:
            file_path = Path(f"target/debug/{package}")
    elif file_path is None and not example:
        # Default: derive binary name from the cwd's Cargo.toml so the path
        # matches what `cargo build` produces.
        file_path = Path(f"target/debug/{_default_package_name()}")

    build_extra = [*shlex.split(build_args), *cargo_package, *cargo_example]
    build_argv, build_env = build.cmd(build_extra)

    if example:
        target_path = Path(f"./target/debug/examples/{example}")
    else:
        assert file_path is not None  # set above when no example
        target_path = file_path

    if assets is not None:
        assets_autodetected: Path | None = assets
    else:
        # `just play` is always invoked from the worktree root, so assets
        # live directly under cwd.
        assets_path = Path.cwd() / "assets"
        assets_autodetected = assets_path if assets_path.exists() else None

    if mode not in _VALID_MODES:
        raise typer.BadParameter(f"--mode must be one of {sorted(_VALID_MODES)}; got {mode!r}")
    if mode == "auto":
        resolved_mode: Literal["local", "remote"] = (
            "remote" if environ.get("SSH_CLIENT") and environ.get("PSYNC_SERVER_IP") else "local"
        )
    else:
        resolved_mode = mode  # type: ignore[assignment]

    return RunPlan(
        target_path=target_path,
        build_argv=build_argv,
        build_env=build_env,
        assets_explicit=assets,
        assets_autodetected=assets_autodetected,
        env_vars=env_vars,
        cmd_args=cmd_args,
        passthrough=tuple(passthrough),
        mode=resolved_mode,
        dry_run=dry_run,
        skip_build=skip_build,
    )


def _log_plan(plan: RunPlan) -> None:
    """Emit a human-readable dump of ``plan`` at dry-run log level."""
    sorted_env = ", ".join(f"{k}={v}" for k, v in sorted(plan.build_env.items()))
    _common.log("dry-run: resolved plan (no build, no exec, no relay)", level="dry")
    _common.log(f"  mode:                {plan.mode}", level="dry")
    _common.log(f"  target_path:         {plan.target_path}", level="dry")
    _common.log(f"  build_argv:          {' '.join(plan.build_argv)}", level="dry")
    _common.log(f"  build_env:           {sorted_env}", level="dry")
    _common.log(f"  assets_explicit:     {plan.assets_explicit}", level="dry")
    _common.log(f"  assets_autodetected: {plan.assets_autodetected}", level="dry")
    _common.log(f"  env_vars:            {plan.env_vars!r}", level="dry")
    _common.log(f"  cmd_args:            {plan.cmd_args!r}", level="dry")
    _common.log(f"  passthrough:         {list(plan.passthrough)!r}", level="dry")


def _exec_remote(plan: RunPlan) -> None:
    """Patchelf the target, then hand off to ``cubething_psync`` via uvx."""
    _patch_elf_for_psync(plan.target_path)

    args = [
        "uvx",
        "--from",
        "cubething_psync",
        "psync",
        str(plan.target_path),
    ]
    if plan.assets_autodetected is not None:
        args += ["-A", str(plan.assets_autodetected)]
    if plan.env_vars is not None:
        args += ["-e", plan.env_vars]
    if plan.cmd_args:
        _common.log(_DEPRECATED_ARGS_MSG, level="warn")
    # psync's ``-a`` accepts a single shell-quoted string (it shlex.splits
    # internally). Merge the legacy ``-a`` value with the new ``--``
    # passthrough so both reach the binary.
    combined = [*shlex.split(plan.cmd_args), *plan.passthrough]
    if plan.cmd_args is not None:
        args += ["-a", shlex.join(combined)]

    _common.run(args)


def _exec_local(plan: RunPlan) -> None:
    """Re-point ``LD_LIBRARY_PATH`` at ``target/debug/deps`` and exec the binary.

    Bevy's ``AssetPlugin`` reads ``CARGO_MANIFEST_DIR`` from the process
    env at runtime (via ``std::env::var``) to locate the assets root.
    ``cargo run`` and ``dx serve`` both inject it at spawn time; a bare
    ``os.execvpe`` does not, which is why ``just play`` used to load
    assets out of ``target/debug/assets`` instead of the crate root.
    Set it explicitly to the cwd so the local exec matches ``cargo run``.

    ``-A`` / ``-e`` are psync-only knobs; passing them through to a local
    exec is not meaningful, so we warn and ignore rather than silently
    drop them on the floor.
    """
    if plan.assets_explicit is not None:
        _common.log("--assets/-A is psync-only and was ignored in local mode", level="warn")
    if plan.env_vars:
        _common.log("--env/-e is psync-only and was ignored in local mode", level="warn")

    if plan.cmd_args:
        _common.log(_DEPRECATED_ARGS_MSG, level="warn")

    deps_dir = Path.cwd() / "target" / "debug" / "deps"
    existing_ld = os.environ.get("LD_LIBRARY_PATH", "")
    run_ld_path = f"{deps_dir}{':' + existing_ld if existing_ld else ''}"

    final = [
        str(plan.target_path),
        *shlex.split(plan.cmd_args),
        *plan.passthrough,
    ]
    env = {
        **os.environ,
        "LD_LIBRARY_PATH": run_ld_path,
        "CARGO_MANIFEST_DIR": str(Path.cwd().resolve()),
    }

    _common.log(" ".join(final), level="info")
    os.execvpe(final[0], final, env)


def _split_passthrough(argv: Sequence[str]) -> list[str]:
    """Return tokens after the first literal ``--`` in ``argv``.

    Click strips the ``--`` sentinel from ``ctx.args`` under
    ``ignore_unknown_options=True``, so we recover the boundary from the
    raw process argv. Returns an empty list when no ``--`` is present.
    Only the *first* ``--`` is treated as the boundary; subsequent
    ``--`` tokens are preserved verbatim in the returned tail.
    """
    try:
        i = list(argv).index("--")
    except ValueError:
        return []
    return list(argv[i + 1 :])


def main(
    ctx: typer.Context,
    example: str | None = typer.Option(
        None,
        "-x",
        "--example",
        help="Run a Cargo example (target/debug/examples/<name>) instead of the default binary.",
    ),
    package: str | None = typer.Option(
        None,
        "-p",
        "--package",
        help="Cargo `-p PACKAGE`. Defaults to `[package].name` from the cwd's Cargo.toml.",
    ),
    build_args: str = typer.Option(
        "-F dylib",
        "-B",
        "--build-args",
        help="Extra args forwarded to `cargo build` (shell-split). Default: `-F dylib`.",
    ),
    env_vars: str = typer.Option(
        "", "-e", "--env", help="Env-var string forwarded to psync (remote mode only)."
    ),
    cmd_args: str = typer.Option(
        "",
        "-a",
        "--args",
        help="(deprecated; use '-- <args>') Args appended to the binary invocation.",
    ),
    assets: Path | None = typer.Option(
        None,
        "-A",
        "--assets",
        help=(
            "Override the assets directory (default: autodetected). "
            "(psync only \u2014 ignored with a warning in local mode)"
        ),
    ),
    mode: str = typer.Option(
        "auto",
        "-m",
        "--mode",
        help=(
            "'auto' (default, picks remote when SSH_CLIENT and PSYNC_SERVER_IP "
            "are both set), 'local' (force local exec), 'remote' (force psync "
            "handoff)."
        ),
    ),
    dry_run: bool = typer.Option(
        False,
        "-n",
        "--dry-run",
        help="Print the resolved plan and exit without building or running anything.",
    ),
    skip_build: bool = typer.Option(
        False,
        "-S",
        "--skip-build",
        help="Skip `cargo build` and reuse the existing target binary.",
    ),
) -> None:
    """Build a Cargo binary and exec it locally or relay it to a psync host."""
    # Click strips ``--`` from ``ctx.args``; reach into ``sys.argv`` to
    # recover the boundary and split ``ctx.args`` accordingly.
    post = _split_passthrough(sys.argv)
    extras_all = list(ctx.args)
    pre = extras_all[: len(extras_all) - len(post)] if post else extras_all
    plan = build_plan(
        example=example,
        package=package,
        build_args=build_args,
        env_vars=env_vars,
        cmd_args=cmd_args,
        assets=assets,
        extras=pre,
        environ=os.environ,
        mode=mode,
        passthrough=post,
        dry_run=dry_run,
        skip_build=skip_build,
    )
    if plan.dry_run:
        _log_plan(plan)
        return
    if not plan.skip_build:
        _common.run(plan.build_argv, env_overrides=plan.build_env)
    if plan.mode == "remote":
        _exec_remote(plan)
    else:
        _exec_local(plan)
