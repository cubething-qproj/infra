# ------------------------------------------
# SPDX-License-Identifier: MIT OR Apache-2.0
# -------------------------------- 𝒒𝒑𝒓𝒐𝒋 --

set allow-duplicate-variables

import 'infra/main/just/shared.just'

mod ws 'infra/main/just/ws.justfile'

scripts := parent_directory(canonicalize(justfile())) / "infra/main/scripts"

_default:
    @just --justfile {{ justfile() }} --list --unsorted

# Regenerate this justfile from infra template.
self-update:
    cp infra/main/metarepo.just justfile

# Switch a repo's `active` symlink to an existing worktree branch.
switch-branch repo branch:
    @just ws wt switch {{ repo }} {{ branch }}
