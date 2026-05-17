"""Generate a coverage report via ``cargo llvm-cov nextest``.

With no forwarded arguments, defaults to ``--html --open`` (HTML report,
opened in a browser).

Forces ``RUSTFLAGS=-Zcodegen-backend=llvm`` so the cranelift backend (default
in our nightly devshell) is bypassed for the instrumented build.
"""

from __future__ import annotations

import typer

from qproj_scripts import _common


def main(ctx: typer.Context) -> None:
    """Run ``cargo llvm-cov nextest`` with the LLVM codegen backend."""
    args = ctx.args if ctx.args else ["--html", "--open"]
    result = _common.run(
        ["cargo", "llvm-cov", "nextest", *args],
        env_overrides={"RUSTFLAGS": "-Zcodegen-backend=llvm"},
        check=False,
    )
    raise typer.Exit(result.returncode)
