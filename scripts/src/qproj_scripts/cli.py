"""Unified CLI frontend for the qproj_scripts verb modules.

Each verb is a ``typer.Typer`` sub-app defined in its own module
(:mod:`qproj_scripts.build`, :mod:`qproj_scripts.play`, ...). This module
mounts them under their CLI names and exposes the resulting top-level
``app`` as the ``qproj-scripts`` console script entry point.

The only verb defined directly in this module is ``fix``, a thin alias
for ``clippy --fix`` that reuses :func:`qproj_scripts.clippy.cmd`.
"""

from __future__ import annotations

import typer

from qproj_scripts import (
    _common,
    bevy_lint,
    build,
    check,
    ci,
    clippy,
    coverage,
    deny,
    play,
    ra_check,
    sync,
    test,
)

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
    help="Unified CLI for the cubething-qproj infra task scripts.",
)

app.add_typer(build.app, name="build", help="Build the workspace.")
app.add_typer(play.app, name="play", help="Build and run a quell binary.")
app.add_typer(check.app, name="check", help="Run Clippy and bevy_lint concurrently.")
app.add_typer(clippy.app, name="clippy", help="Run Clippy.")
app.add_typer(bevy_lint.app, name="bevy-lint", help="Run bevy_lint.")
app.add_typer(deny.app, name="deny", help="Audit dependencies via cargo deny.")
app.add_typer(test.app, name="test", help="Run the workspace test suite via nextest.")
app.add_typer(coverage.app, name="coverage", help="Generate a coverage report.")
app.add_typer(ci.app, name="ci", help="Run GitHub Actions workflows locally via act.")
app.add_typer(
    ra_check.app,
    name="ra-check",
    help="Emit Clippy + bevy_lint diagnostics as JSON for rust-analyzer.",
)
app.add_typer(
    sync.app,
    name="sync",
    help="Sync the local clone-tree of workflow consumer repos.",
)


@app.command(
    name="fix",
    context_settings={
        "allow_extra_args": True,
        "ignore_unknown_options": True,
        "help_option_names": ["-h", "--help"],
    },
    help="Run Clippy with --fix to apply autofixable suggestions.",
)
def fix(ctx: typer.Context) -> None:
    """Run ``cargo clippy --fix --all-features --target-dir=target/clippy``."""
    argv, env = clippy.cmd(["--fix", *ctx.args])
    result = _common.run(argv, env_overrides=env or None, check=False)
    raise typer.Exit(result.returncode)
