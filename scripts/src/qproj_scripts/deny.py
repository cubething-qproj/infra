"""Audit dependencies via ``cargo deny``.

Runs the advisories, bans, and sources checks across the whole workspace at
log-level error, with the dependency-inclusion graph hidden for terser output.
"""

from __future__ import annotations

import typer

from qproj_scripts import _common

app = typer.Typer(
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.callback(invoke_without_command=True)
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
    raise typer.Exit(result.returncode)
