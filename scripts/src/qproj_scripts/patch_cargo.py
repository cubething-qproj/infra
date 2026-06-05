"""Deep-merge a shared workspace template into a downstream ``Cargo.toml``.

The template is treated as a **minimal required set**: every key path
present in the template must be present in the target with the
template's value. Keys present in the target but absent from the
template are left untouched.

Merge rules (recursive, depth-first):

* Nested tables (``[a.b]``, ``[a.b.c]``) are recursed into. Existing
  keys in the target table that aren't in the template's table are
  preserved.
* Inline tables (``key = { x = 1, y = 2 }``), arrays, and scalars are
  treated as opaque values and overwritten wholesale when the
  template specifies them.
* Tables in the target that aren't in the template are left alone.

This means the template never *removes* anything from a downstream
manifest; it only ensures the shared baseline is present and current.
Downstreams are free to add their own ``[workspace.members]``,
extra ``[profile.*]`` entries, etc., without the patcher fighting
them.

The operation is idempotent: running it twice on the same input
produces the same output as running it once.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import tomlkit
import typer
from tomlkit.container import Container
from tomlkit.items import Table

from qproj_scripts._common import log


def _is_table(value: Any) -> bool:
    """True iff ``value`` is a TOML table (recursable), not an inline table.

    Inline tables (``{ a = 1, b = 2 }``) are semantically a single
    value in Cargo manifests (e.g. ``rust.unexpected_cfgs = { level
    = "warn", ... }``) and are treated as opaque scalars.
    """
    return isinstance(value, (Table, Container))


def _deep_merge(target: Any, template: Any) -> None:
    """Recursively ensure every key in ``template`` is set in ``target``."""
    for key, tpl_value in template.items():
        if _is_table(tpl_value) and key in target and _is_table(target[key]):
            _deep_merge(target[key], tpl_value)
        else:
            target[key] = tpl_value


def patch(target_text: str, template_text: str) -> str:
    """Return ``target_text`` deep-merged with ``template_text``.

    Pure function; performs no I/O. Round-trips through ``tomlkit`` so
    untouched tables retain their original formatting.
    """
    target = tomlkit.parse(target_text)
    template = tomlkit.parse(template_text)
    _deep_merge(target, template)
    return tomlkit.dumps(target)


def main(
    target: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        writable=True,
        help="Path to the downstream Cargo.toml to patch in place.",
    ),
    template: Path = typer.Option(
        ...,
        "--template",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to the shared Cargo.workspace.toml template.",
    ),
    check: bool = typer.Option(
        False,
        "--check",
        help="Exit non-zero if the target would change; do not write.",
    ),
) -> None:
    """Patch ``target`` in place by deep-merging ``template`` into it."""
    original = target.read_text()
    patched = patch(original, template.read_text())

    if patched == original:
        log(f"{target}: already in sync", level="info")
        return

    if check:
        log(f"{target}: out of sync with {template}", level="error")
        raise typer.Exit(code=1)

    log(f"patch {target}", level="info")
    target.write_text(patched)
