"""Audit dependencies via ``cargo deny``.

Runs the advisories, bans, and sources checks across the whole workspace at
log-level error, with the dependency-inclusion graph hidden for terser output.
"""

from __future__ import annotations

import typer

from qproj_scripts import _common


def main() -> None:
    """Run ``cargo deny check advisories bans sources``."""
    result = _common.run(
        [
            "cargo",
            "deny",
            "--workspace",
            "-L",
            "error",
            "check",
            "advisories",
            "bans",
            "sources",
            "--hide-inclusion-graph",
        ],
        check=False,
    )
    raise typer.Exit(result.returncode)  # pyright: ignore[reportOptionalMemberAccess]
