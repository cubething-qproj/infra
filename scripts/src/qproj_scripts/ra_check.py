"""Emit Clippy + bevy_lint diagnostics in JSON form for rust-analyzer.

Configured in the editor as the ``check.overrideCommand`` so RA shows
both Clippy lints and bevy_lint lints as inline diagnostics. Each linter
gets an isolated target dir to avoid step-on-toes incremental rebuilds.

Does not share command construction with :mod:`qproj_scripts.clippy` /
:mod:`qproj_scripts.bevy_lint` because the JSON output flag, isolated
target dirs, and direct ``bevy_lint`` driver invocation (vs ``bevy lint``)
are RA-specific.
"""

from __future__ import annotations

import subprocess

import typer

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
    """Run Clippy then bevy_lint, both with JSON-rendered-ANSI diagnostics."""
    extra = list(ctx.args)

    clippy_rc = subprocess.run(
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

    bevy_rc = subprocess.run(
        [
            "bevy_lint",
            "--all-features",
            "--target-dir=target/ra-bevy-lint",
            "--message-format=json-diagnostic-rendered-ansi",
            *extra,
        ],
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode

    raise typer.Exit(clippy_rc or bevy_rc)
