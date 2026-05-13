"""Build the workspace.

Thin wrapper over ``cargo build``. All extra arguments are forwarded.
Pins ``RUSTC_WRAPPER=sccache`` for shared incremental cache hits.
"""

from __future__ import annotations

import typer

from qproj_scripts import _common

app = typer.Typer(
    add_completion=False,
    context_settings={
        "allow_extra_args": True,
        "ignore_unknown_options": True,
        "help_option_names": ["-h", "--help"],
    },
)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Run ``cargo build`` with any forwarded arguments."""
    result = _common.run(
        ["cargo", "build", *ctx.args],
        check=False,
        env_overrides={"RUSTC_WRAPPER": "sccache"},
    )
    raise typer.Exit(result.returncode)
