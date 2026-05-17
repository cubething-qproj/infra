"""Run the workspace test suite via ``cargo nextest``.

With no arguments, runs ``r --workspace`` (run all tests). With arguments,
forwards them verbatim. Always pins ``--config-file=./.config/nextest.toml``.
"""

from __future__ import annotations

import typer

from qproj_scripts import _common


def main(ctx: typer.Context) -> None:
    """Run ``cargo nextest`` with the workspace nextest config."""
    base = ["cargo", "nextest"]
    cmd = base + (ctx.args if ctx.args else ["r", "--workspace"])
    result = _common.run(cmd, check=False, env_overrides={"RUSTC_WRAPPER": "sccache"})
    raise typer.Exit(result.returncode)  # pyright: ignore[reportOptionalMemberAccess]
