# ------------------------------------------
# SPDX-License-Identifier: MIT OR Apache-2.0
# -------------------------------- 𝒒𝒑𝒓𝒐𝒋 --

import 'shared.just'

mod ws 'ws.justfile'

# Lint GitHub Actions workflows.
actionlint:
    actionlint

# Manage worktrees: wt add|switch|rm|ls|status
wt *args:
    {{scripts}}/wt.sh {{args}}
