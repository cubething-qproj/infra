"""Patch a downstream ``Cargo.toml`` with the shared workspace template.

This verb implements the merge half of the
``infra-sync-downstream`` flow: the file-copy loop handles single-file
syncs (``deny.toml``, ``flake.nix``, ...), but ``Cargo.toml`` cannot
just be overwritten because each downstream repo owns the
``[package]`` / ``[dependencies]`` / ``[features]`` / ``[[bin]]`` tables
that describe its own crate. So instead of copying, we *patch* the
target file: replace the shared tables wholesale from the template,
leave everything else untouched.

Tables replaced wholesale (presence in the template is authoritative):

* ``[workspace]``
* ``[workspace.lints]``
* every ``[profile.*]`` / ``[profile.*.*]`` table

A top-level ``[lints]`` table with ``workspace = true`` is also
ensured (no-op if the manifest is a pure virtual workspace; for
hybrid workspace+package manifests it wires the package's lints to
the workspace block we just installed).

Everything else in the target manifest is preserved verbatim,
including key order and formatting -- the patcher uses ``tomlkit``
for a round-trip-preserving edit.

The operation is idempotent: a second invocation against
already-patched content produces zero diff.
"""

from __future__ import annotations

from pathlib import Path

import tomlkit
import typer
from tomlkit import TOMLDocument
from tomlkit.items import Table

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
    #    [workspace.lints]) wholesale. We treat the entire [workspace]
    #    subtree as template-owned.
    if "workspace" in template:
        target["workspace"] = template["workspace"]
    elif "workspace" in target:
        del target["workspace"]

    # 2. Replace the entire [profile] subtree wholesale. Per the plan
    #    there is no per-repo profile override mechanism, so any
    #    [profile.*] not in the template should be dropped.
    if "profile" in template:
        target["profile"] = template["profile"]
    elif "profile" in target:
        del target["profile"]

    # 3. Ensure top-level [lints] workspace = true so per-crate
    #    manifests inherit the workspace lints block we just installed.
    lints = target.get("lints")
    if not isinstance(lints, Table):
        lints = tomlkit.table()
        target["lints"] = lints
    lints["workspace"] = True

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
