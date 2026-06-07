"""Emit Clippy diagnostics in JSON form for rust-analyzer.

Configured in the editor as the ``check.overrideCommand`` so RA shows
Clippy lints as inline diagnostics. Isolated target dir keeps incremental
caches separate from plain ``cargo build``.
"""

from __future__ import annotations

import subprocess

import typer


def main(ctx: typer.Context) -> None:
    """Run Clippy with JSON-rendered-ANSI diagnostics."""
    extra = list(ctx.args)
    rc = subprocess.run(
        [
            "cargo",
            "clippy",
            "--all-features",
            "--target-dir=target/ra-clippy",
            "--message-format=json-diagnostic-rendered-ansi",
            *extra,
        ],
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode
    raise typer.Exit(rc)
