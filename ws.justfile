# ------------------------------------------
# SPDX-License-Identifier: MIT OR Apache-2.0
# -------------------------------- 𝒒𝒑𝒓𝒐𝒋 --
#
# Workspace recipes — thin wrappers over the pj submodule's scripts.
#
# pj's own justfile hardcodes `ROOT := parent_directory(justfile_directory())`,
# which is wrong when pj is checked out as a submodule at infra/main/pj/.
# We sidestep that by calling pj's scripts directly and letting them read
# $PROJECT_ROOT from the environment (set by the metarepo's root .envrc).

set shell := ["bash", "-euo", "pipefail", "-c"]

PJ := justfile_directory() / "pj"
SCRIPTS := PJ / "scripts"

_default:
    @just --justfile {{ justfile() }} --list --unsorted

# Point basedpyright at a Python interpreter (accepts a venv dir or python binary).
venv *ARGS:
    uv run --script {{ SCRIPTS }}/pyright.py {{ ARGS }}

# Workspace health-check.
doctor *ARGS:
    uv run --script {{ SCRIPTS }}/doctor.py {{ ARGS }}

# Clean stale worktrees / branches across primary repos.
clean *ARGS:
    uv run --script {{ SCRIPTS }}/clean.py {{ ARGS }}

# Install shared git hooks into primary repos.
install-git *ARGS:
    bash {{ SCRIPTS }}/install-git.sh {{ ARGS }}
