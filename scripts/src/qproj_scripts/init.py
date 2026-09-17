"""Initialize an ordinary downstream checkout under ``cubething-qproj/<name>``.

Optionally creates the GitHub remote, scaffolds a Cargo project, commits
and pushes it, then installs the shared local project configuration.
Defaults to dry-run; pass ``-x`` / ``--execute`` to mutate.
"""

from __future__ import annotations

import json
import os
import shutil
from importlib.resources import as_file
from pathlib import Path

import typer

from qproj_scripts import patch_cargo
from qproj_scripts._common import DEFAULT_BRANCH, DEFAULT_REMOTE, asset, log, run
from qproj_scripts.sync import _sync_repo, envrc, write_file

ORG = "cubething-qproj"

# Files in the project-template that get {{name}} substitution before
# being written. Everything else is copied verbatim.
_TEMPLATED = frozenset({"Cargo.toml", "README.md"})


def _default_infra_dir() -> Path:
    home = Path.home()
    base_dir = Path(os.environ.get("BASE_DIR", str(home / "repos")))
    return base_dir / ORG / "infra"


def _write(path: Path, content: str, *, dry: bool) -> None:
    write_file(path, content, dry=dry)


def _copy(src: Path, dst: Path, *, dry: bool) -> None:
    level = "dry" if dry else "info"
    log(f"cp {src} -> {dst}", level=level)
    if dry:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


def _render_project(name: str, dest: Path, infra_dir: Path, *, bin_: bool, dry: bool) -> None:
    """Lay down the per-project scaffold + shared files into ``dest``."""
    level = "dry" if dry else "info"

    # 1. Per-project files from the package template.
    skip = {"src/main.rs"} if not bin_ else {"src/lib.rs"}
    with as_file(asset("project-template")) as tmpl_root:
        for src in sorted(tmpl_root.rglob("*")):
            if src.is_dir():
                continue
            rel = src.relative_to(tmpl_root)
            if str(rel) in skip:
                continue
            dst = dest / rel
            if rel.name in _TEMPLATED:
                text = src.read_text().replace("{{name}}", name)
                _write(dst, text, dry=dry)
            else:
                _copy(src, dst, dry=dry)

    # 2. Copy LICENSE files verbatim from infra.
    for lic in ("LICENSE-MIT.txt", "LICENSE-APACHE.txt"):
        _copy(infra_dir / lic, dest / lic, dry=dry)

    # 3. Apply sync-files.json (shared checkout files: deny.toml,
    #    flake.nix, ci.yml, .cargo/config.toml, justfile, nextest.toml).
    sync_files = json.loads((infra_dir / "sync-files.json").read_text())
    for entry in sync_files:
        _copy(infra_dir / entry["src"], dest / entry["dst"], dry=dry)

    # 4. Patch shared workspace/profile/lints into Cargo.toml.
    cargo = dest / "Cargo.toml"
    template_cargo = infra_dir / "config" / "Cargo.workspace.toml"
    log(f"patch_cargo {cargo}", level=level)
    if not dry:
        cargo.write_text(patch_cargo.patch(cargo.read_text(), template_cargo.read_text()))


def _bootstrap_in_place(
    name: str,
    repo_dir: Path,
    remote_url: str,
    infra_dir: Path,
    *,
    project: bool,
    bin_: bool,
    dry: bool,
) -> None:
    """Initialize an ordinary checkout in its final location, commit, and push."""
    level = "dry" if dry else "info"
    run(["git", "init", "-b", DEFAULT_BRANCH, str(repo_dir)], dry=dry)
    run(["git", "-C", str(repo_dir), "remote", "add", DEFAULT_REMOTE, remote_url], dry=dry)

    if project:
        _render_project(name, repo_dir, infra_dir, bin_=bin_, dry=dry)
    else:
        readme = repo_dir / "README.md"
        log(f"write {readme}", level=level)
        if not dry:
            readme.write_text(f"# {name}\n")

    run(["git", "-C", str(repo_dir), "add", "."], dry=dry)
    run(["git", "-C", str(repo_dir), "commit", "-m", "chore: initial commit"], dry=dry)
    run(["git", "-C", str(repo_dir), "push", "-u", DEFAULT_REMOTE, DEFAULT_BRANCH], dry=dry)


def main(
    name: str = typer.Argument(
        ...,
        help="Repo name (without org), e.g. q_widgets. Must not contain '/'.",
    ),
    create_remote: bool = typer.Option(
        True,
        "--create-remote/--no-create-remote",
        help="Create the GitHub repo via `gh repo create` before cloning.",
    ),
    private: bool = typer.Option(
        True,
        "--private/--public",
        help="Visibility passed to `gh repo create`. Ignored without --create-remote.",
    ),
    project: bool = typer.Option(
        True,
        "--project/--no-project",
        help="Scaffold a Cargo project before the initial commit.",
    ),
    bin_: bool = typer.Option(
        False,
        "--bin/--lib",
        help="Scaffold a binary crate (src/main.rs) instead of a library (src/lib.rs).",
    ),
    infra_dir: Path = typer.Option(
        None,
        "--infra-dir",
        help="Path to the infra working tree (source of sync-files.json, "
        "LICENSE files, Cargo.workspace.toml). "
        "Defaults to $BASE_DIR/cubething-qproj/infra.",
    ),
    execute: bool = typer.Option(
        False,
        "-x",
        "--execute",
        help="Actually run mutating commands (default is dry-run).",
    ),
    clobber: bool = typer.Option(
        False,
        "--clobber",
        help="Wipe the target repo dir if it already exists and is non-empty.",
    ),
) -> None:
    """Initialize a new downstream repo under cubething-qproj/<name>."""
    if "/" in name or not name:
        log(f"Invalid repo name: {name!r} (must not contain '/')", level="error")
        raise typer.Exit(code=1)

    full = f"{ORG}/{name}"
    dry = not execute

    # Refuse to re-init an already-registered repo.
    downstream_repos_text = asset("downstream-repos.json").read_text("utf8")
    downstream_repos = json.loads(downstream_repos_text)
    if full in downstream_repos:
        log(f"{full} already in downstream-repos.json", level="error")
        raise typer.Exit(code=1)

    home = Path.home()
    base_dir = Path(os.environ.get("BASE_DIR", str(home / "repos")))
    org_dir = base_dir / ORG
    config_dir = org_dir / ".config"
    repo_dir = base_dir / full
    infra_dir = (infra_dir or _default_infra_dir()).resolve()

    # Sanity-check infra_dir before we touch anything.
    if project:
        missing = [
            p
            for p in (
                "sync-files.json",
                "LICENSE-MIT.txt",
                "LICENSE-APACHE.txt",
                "config/Cargo.workspace.toml",
            )
            if not (infra_dir / p).is_file()
        ]
        if missing:
            log(f"--infra-dir {infra_dir} missing: {', '.join(missing)}", level="error")
            raise typer.Exit(code=1)

    if repo_dir.exists() and any(repo_dir.iterdir()):
        if not clobber:
            log(
                f"{repo_dir} already exists and is non-empty. Re-run with --clobber to wipe it.",
                level="error",
            )
            raise typer.Exit(code=1)
        log(f"--clobber: rm -rf {repo_dir}", level="dry" if dry else "warn")
        if not dry:
            shutil.rmtree(repo_dir)

    # Ensure shared org-level config + .envrc exist (mirrors sync.main's
    # top block). Duplicated for now; dedupe candidate for later.
    level = "dry" if dry else "info"
    with as_file(asset(".config")) as src:
        log(f"rm -rf {config_dir}", level)
        if not dry:
            shutil.rmtree(config_dir, ignore_errors=True)
        log(f"cp -r {src} -> {config_dir}", level)
        if not dry:
            shutil.copytree(src, config_dir)
    log("writing .envrc", "info")
    write_file(org_dir / ".envrc", envrc(), dry=dry)

    # Create the remote and initialize the ordinary checkout in place.
    if create_remote:
        visibility = "--private" if private else "--public"
        run(["gh", "repo", "create", full, visibility], dry=dry)
        remote_url = f"git@github.com:{full}.git"
        _bootstrap_in_place(
            name,
            repo_dir,
            remote_url,
            infra_dir,
            project=project,
            bin_=bin_,
            dry=dry,
        )
    else:
        log(
            f"--no-create-remote: assuming {full} already exists with origin/main",
            level="info",
        )

    # Fetch the checkout and install local project configuration (idempotent).
    _sync_repo(full, base_dir, config_dir, dry=dry)

    # Register in downstream-repos.json so future `sync` runs pick it up.
    new_repos = [*downstream_repos, full]
    with as_file(asset("downstream-repos.json")) as p:
        log(f"update {p}", level)
        if not dry:
            p.write_text(json.dumps(new_repos, indent=2) + "\n")

    log(f"initialized {full} at {repo_dir}", level="info")
    if project:
        log(f"next: cd {repo_dir} && just sync-scripts && just build", level="info")
