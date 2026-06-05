"""Patch a downstream ``Cargo.toml`` with the shared workspace template.

The sync workflow can't just overwrite a downstream ``Cargo.toml`` --
each repo owns its own ``[package]`` / ``[dependencies]`` /
``[features]`` / ``[[bin]]`` tables. So instead of copying, this verb
*patches*: replaces the shared tables wholesale from the template,
leaves everything else untouched.

Tables replaced wholesale (presence in the template is authoritative):

* ``[workspace]``
* ``[workspace.lints]``
* every ``[profile.*]`` / ``[profile.*.*]`` table

A top-level ``[lints]`` table with ``workspace = true`` is also
ensured (no-op for pure virtual workspaces; for hybrid
workspace+package manifests it wires the package's lints to the
workspace block).

Everything else in the target manifest is preserved verbatim,
including key order and formatting -- the patcher uses ``tomlkit``
for a round-trip-preserving edit.

The operation is idempotent.
"""

from __future__ import annotations

from pathlib import Path

import tomlkit
import typer
from tomlkit import TOMLDocument

from qproj_scripts._common import log

# Top-level tables that are owned by the template and replaced wholesale.
_SHARED_TOP_LEVEL = ("workspace",)


def _shared_top_level(key: str) -> bool:
    return key in _SHARED_TOP_LEVEL or key == "profile" or key.startswith("profile.")


def _replace_table(doc: TOMLDocument, key: str, value: object) -> None:
    """Overwrite ``doc[key]`` with ``value`` (or remove the key when value is None)."""
    if value is None:
        if key in doc:
            del doc[key]
        return
    doc[key] = value


def patch(target_text: str, template_text: str) -> str:
    """Return ``target_text`` patched with shared tables from ``template_text``.

    Pure function; performs no I/O. Round-trips through ``tomlkit`` so
    untouched tables retain their original formatting.
    """
    target = tomlkit.parse(target_text)
    template = tomlkit.parse(template_text)

    # 1. Replace [workspace] and any nested [workspace.*] (notably
    #    [workspace.lints]) wholesale -- the entire [workspace]
    #    subtree is template-owned.
    if "workspace" in template:
        target["workspace"] = template["workspace"]
    elif "workspace" in target:
        del target["workspace"]

    # 2. Replace the entire [profile] subtree wholesale. There is no
    #    per-repo profile override mechanism, so any [profile.*] not
    #    in the template is dropped.
    if "profile" in template:
        target["profile"] = template["profile"]
    elif "profile" in target:
        del target["profile"]

    # 3. Replace [lints] wholesale with a single `workspace = true`
    #    entry. Cargo refuses to mix workspace inheritance with any
    #    other keys under [lints]; the per-crate overrides we're
    #    discarding here are the same content we just injected into
    #    [workspace.lints].
    lints = tomlkit.table()
    lints["workspace"] = True
    target["lints"] = lints

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
    """Patch ``target`` in place with shared tables from ``template``."""
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
