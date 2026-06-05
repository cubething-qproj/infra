"""Check out a branch in the metarepo's ``active/`` worktree.

Pre-Step-4 this verb retargeted a symlink (``ln -s <dir> active``).
Post-Step-4 ``active/`` is a real ``git worktree``: ``target`` now
fetches and runs ``git checkout`` inside it. The verb still operates
from the metarepo root (the dir that contains ``.bare/`` and
``active/``).

Semantics:

* ``qproj target <branch>``  -- checkout an existing branch (local
  or remote) in ``active/``. The branch name has no prefix
  restriction in this case.
* ``qproj target <branch>``  -- if the branch doesn't yet exist
  anywhere, the name must match one of the canonical prefixes
  (``fix/``, ``feat/``, ``doc/``, ``tests/``, ``release/``); a fresh
  branch is created from ``$DEFAULT_REMOTE/$DEFAULT_BRANCH``.
* ``qproj target default``   -- shorthand for the default branch.
* ``--clobber``               -- proceed even if ``active/`` has
  uncommitted changes (passes ``-f`` to ``git checkout``).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import typer

from qproj_scripts import _common
from qproj_scripts._common import DEFAULT_BRANCH, DEFAULT_REMOTE, PREFIX_RE, log, run


def _ref_exists(active: Path, ref: str) -> bool:
    """True iff ``ref`` resolves inside the ``active`` worktree's repo."""
    result = subprocess.run(
        ["git", "-C", str(active), "rev-parse", "--verify", "--quiet", ref],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _is_dirty(active: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(active), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    )
    return bool(result.stdout.strip())


def retarget(target: str, *, clobber: bool = False) -> None:
    """Check out ``target`` in ``./active/``.

    ``target == "default"`` is shorthand for ``$DEFAULT_BRANCH``. The
    caller is expected to be cwd'd at the metarepo root.
    """
    if target == "default":
        target = DEFAULT_BRANCH

    active = Path("active")
    if not active.is_dir():
        log(
            f"{active.resolve()} is not a directory. Run `qproj sync -x` first.",
            level="error",
        )
        raise typer.Exit(code=1)

    if _is_dirty(active) and not clobber:
        log(
            f"{active} has uncommitted changes. Re-run with --clobber to overwrite.",
            level="error",
        )
        raise typer.Exit(code=1)

    run(["git", "-C", str(active), "fetch", DEFAULT_REMOTE])

    local = _ref_exists(active, f"refs/heads/{target}")
    remote = _ref_exists(active, f"refs/remotes/{DEFAULT_REMOTE}/{target}")
    checkout = ["git", "-C", str(active), "checkout"]
    if clobber:
        checkout.append("-f")

    if local:
        run([*checkout, target])
    elif remote:
        # Create / fast-forward a local tracking branch from the remote.
        run([*checkout, "-B", target, f"{DEFAULT_REMOTE}/{target}"])
    else:
        if not PREFIX_RE.match(target):
            log(f"Invalid new-branch name: {target}", level="error")
            log(
                "New branches must be one of: fix/*, feat/*, doc/*, tests/*, release/*.",
                level="error",
            )
            raise typer.Exit(code=1)
        run([*checkout, "-B", target, f"{DEFAULT_REMOTE}/{DEFAULT_BRANCH}"])

    _common.run(["git", "-C", str(active), "log", "-1", "--oneline"])


def main(
    branch: str = typer.Argument(
        ...,
        metavar="BRANCH",
        help="Branch to check out in active/. Use 'default' for the default branch.",
    ),
    clobber: bool = typer.Option(
        False,
        "--clobber",
        help="Force the checkout even when active/ has uncommitted changes.",
    ),
) -> None:
    retarget(branch, clobber=clobber)
