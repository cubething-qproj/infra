"""Run the workspace test suite via ``cargo nextest``.

With no arguments, runs ``r --workspace`` (run all tests). With arguments,
forwards them verbatim. Always pins ``--config-file=./.config/nextest.toml``.
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
    """Run ``cargo nextest`` with the workspace nextest config."""
    base = ["cargo", "nextest", "--config-file=./.config/nextest.toml"]
    cmd = base + (ctx.args if ctx.args else ["r", "--workspace"])
    result = _common.run(cmd, check=False, env_overrides={"RUSTC_WRAPPER": "sccache"})
    raise typer.Exit(result.returncode)
