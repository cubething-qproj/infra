"""Run Clippy with the workspace's standard flags.

Pins ``--target-dir=target/clippy`` so Clippy's incremental cache does not
collide with plain ``cargo build`` or ``bevy_lint``.
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


def cmd(extra: list[str]) -> tuple[list[str], dict[str, str]]:
    """Return the ``(argv, env_overrides)`` for the standard Clippy invocation.

    Exposed so :mod:`qproj_scripts.check` can launch Clippy in parallel with
    ``bevy_lint`` without re-entering a Python interpreter.
    """
    argv = ["cargo", "clippy", "--all-features", "--target-dir=target/clippy", *extra]
    return argv, {}


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Run ``cargo clippy --all-features --target-dir=target/clippy``."""
    argv, env = cmd(ctx.args)
    result = _common.run(argv, env_overrides=env or None, check=False)
    raise typer.Exit(result.returncode)
