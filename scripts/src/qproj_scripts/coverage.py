"""Generate a coverage report via ``cargo llvm-cov nextest``.

With no forwarded arguments, defaults to ``--html --open`` (HTML report,
opened in a browser).
"""

from __future__ import annotations

import typer

from qproj_scripts import _common


def main(ctx: typer.Context) -> None:
    """Run ``cargo llvm-cov nextest``."""
    args = ctx.args if ctx.args else ["--html", "--open"]
    result = _common.run(["cargo", "llvm-cov", "nextest", *args], check=False)
    raise typer.Exit(result.returncode)  # pyright: ignore[reportOptionalMemberAccess]
