"""Unified CLI frontend for the qproj_scripts verb modules.

Each verb is a plain ``main`` function defined in its own module
(:mod:`qproj_scripts.build`, :mod:`qproj_scripts.play`, ...). This module
registers each as a top-level Typer command on the shared :data:`app`,
which is the ``qproj-scripts`` console script entry point.

Verbs are registered with ``@app.command`` (not ``add_typer``) on purpose:
sub-Typers become Click *groups*, and Click parses any leading ``-x`` on
a group as an attempted subcommand name. Registering as a command makes
each verb a Click *leaf*, where ``allow_extra_args`` /
``ignore_unknown_options`` actually take effect and pass-through args
like ``qproj-scripts build -F dylib`` reach ``cargo`` intact.

The only verb defined directly in this module is ``fix``, a thin alias
for ``clippy --fix`` that reuses :func:`qproj_scripts.clippy.cmd`.
"""

from __future__ import annotations

import typer

from qproj_scripts import (
    _common,
    add,
    bevy_lint,
    build,
    check,
    ci,
    clippy,
    coverage,
    deny,
    init,
    patch_cargo,
    play,
    prune,
    ra_check,
    sync,
    target,
    test,
)

# Verbs that forward all extra args/options to an underlying tool (cargo,
# bevy, act, ...). They must tolerate unknown options so that flags like
# `-F dylib` or `--release` pass through instead of being parsed as
# qproj-scripts options.
_PASSTHROUGH = {
    "allow_extra_args": True,
    "ignore_unknown_options": True,
    "help_option_names": ["-h", "--help"],
}

# Verbs with a fixed, fully-declared option/argument surface.
_STRICT = {"help_option_names": ["-h", "--help"]}

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    context_settings=_STRICT,
    help="Unified CLI for the cubething-qproj infra task scripts.",
)


def _register(name: str, fn, *, ctx, help: str) -> None:
    app.command(name=name, context_settings=ctx, help=help)(fn)


_register("build", build.main, ctx=_PASSTHROUGH, help="Build the workspace.")
_register("play", play.main, ctx=_PASSTHROUGH, help="Build and run a quell binary.")
_register("check", check.main, ctx=_STRICT, help="Run Clippy and bevy_lint concurrently.")
_register("clippy", clippy.main, ctx=_PASSTHROUGH, help="Run Clippy.")
_register("bevy-lint", bevy_lint.main, ctx=_PASSTHROUGH, help="Run bevy_lint.")
_register("deny", deny.main, ctx=_STRICT, help="Audit dependencies via cargo deny.")
_register("test", test.main, ctx=_PASSTHROUGH, help="Run the workspace test suite via nextest.")
_register("coverage", coverage.main, ctx=_PASSTHROUGH, help="Generate a coverage report.")
_register("ci", ci.main, ctx=_PASSTHROUGH, help="Run GitHub Actions workflows locally via act.")
_register(
    "ra-check",
    ra_check.main,
    ctx=_PASSTHROUGH,
    help="Emit Clippy + bevy_lint diagnostics as JSON for rust-analyzer.",
)
_register(
    "sync",
    sync.main,
    ctx=_STRICT,
    help="Sync the local clone-tree of workflow consumer repos.",
)
_register("target", target.main, ctx=_STRICT, help="Check out a branch in active/.")
_register("add", add.main, ctx=_STRICT, help="Create a new worktree off origin/$DEFAULT_BRANCH.")
_register(
    "init",
    init.main,
    ctx=_STRICT,
    help="Initialize a new downstream repo under cubething-qproj/.",
)
_register("prune", prune.main, ctx=_STRICT, help="Clean up all already-merged worktrees.")
_register(
    "patch-cargo",
    patch_cargo.main,
    ctx=_STRICT,
    help="Patch a downstream Cargo.toml with the shared workspace template.",
)


@app.command(
    name="fix",
    context_settings=_PASSTHROUGH,
    help="Run Clippy with --fix to apply autofixable suggestions.",
)
def fix(ctx: typer.Context) -> None:
    """Run ``cargo clippy --fix --all-features --target-dir=target/clippy``."""
    argv, env = clippy.cmd(["--fix", *ctx.args])
    result = _common.run(argv, env_overrides=env or None, check=False)
    raise typer.Exit(result.returncode)  # pyright: ignore[reportOptionalMemberAccess]
