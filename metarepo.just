# ------------------------------------------
# SPDX-License-Identifier: MIT OR Apache-2.0
# -------------------------------- 𝒒𝒑𝒓𝒐𝒋 --

set allow-duplicate-variables

import 'infra/main/shared.just'

scripts := parent_directory(canonicalize(justfile())) / "infra/main/scripts"

# Manage worktrees: wt add|switch|rm|ls|status
wt *args:
    {{scripts}}/wt.sh {{args}}

# Regenerate this justfile from infra template.
self-update:
    cp infra/main/metarepo.just justfile
