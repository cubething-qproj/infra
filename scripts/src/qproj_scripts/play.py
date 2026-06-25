"""Run a freshly-built quell binary, with ergonomic local + remote (psync) modes.

Local mode (no ``$SSH_CLIENT``):
  Re-adds ``target/debug/deps`` to ``LD_LIBRARY_PATH`` so dylib-feature builds
  resolve ``libbevy_dylib-<hash>.so`` under nix-shell, then exec's the binary.
  GPU driver wrapping (nixGL) is the caller's responsibility -- the `play`
  recipe in the shared justfile prepends a `nix run ...#nixVulkan<Vendor>`.

Remote mode (``$SSH_CLIENT`` set):
  patchelf-rewrites the binary so it loads through the host's standard
  loader + a /home/psync/lib RPATH, rsyncs libstd / libbevy_dylib to the
  psync server, and hands off to ``cubething_psync`` via uvx.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import tomllib
from pathlib import Path

import typer

from qproj_scripts import _common, build

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


def main(
    ctx: typer.Context,
    example: str | None = typer.Option(None, "-x", "--example", help="Cargo --example name."),
    package: str | None = typer.Option(None, "-p", "--package", help="Cargo -p package."),
    build_args: str = typer.Option(
        "-F dylib", "-B", "--build-args", help="Extra args forwarded to cargo build."
    ),
    env_vars: str = typer.Option(
        "", "-e", "--env", help="Env-var string forwarded to psync (remote mode only)."
    ),
    cmd_args: str = typer.Option(
        "", "-a", "--args", help="Args appended to the binary invocation."
    ),
    assets: Path | None = typer.Option(
        None,
        "-A",
        "--assets",
        help="Override the assets directory (default: autodetected).",
    ),
) -> None:
    """Build, then exec/relay the binary locally or to the psync host."""
    file_set = False
    file_path: Path | None = None
    extras = list(ctx.args)
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

    # Build via the sibling build verb (in-process).
    build_extra = [*shlex.split(build_args), *cargo_package, *cargo_example]
    build_argv, build_env = build.cmd(build_extra)
    _common.run(build_argv, env_overrides=build_env)

    if example:
        target_path = Path(f"./target/debug/examples/{example}")
    else:
        assert file_path is not None  # set above when no example
        target_path = file_path

    args = [
        "uvx",
        "--from",
        "cubething_psync",
        "psync",
        str(target_path),
    ]
    if assets is not None:
        args += ["-A", str(assets)]
    else:
        # `just play` is always invoked from the worktree root, so assets
        # live directly under cwd.
        assets_path = Path.cwd() / "assets"
        if assets_path.exists():
            args += ["-A", str(assets_path)]

    if env_vars is not None:
        args += ["-e", env_vars]
    if cmd_args is not None:
        args += ["-a", cmd_args]

    if os.environ.get("SSH_CLIENT"):
        _patch_elf_for_psync(target_path)
        _common.run(args)
        return

    # Local exec path.
    deps_dir = Path.cwd() / "target" / "debug" / "deps"
    existing_ld = os.environ.get("LD_LIBRARY_PATH", "")
    run_ld_path = f"{deps_dir}{':' + existing_ld if existing_ld else ''}"

    final = [str(target_path), *shlex.split(cmd_args)]

    _common.log(" ".join(final))
    os.environ["LD_LIBRARY_PATH"] = run_ld_path
    os.execvp(final[0], final)
