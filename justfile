# ------------------------------------------
# SPDX-License-Identifier: MIT OR Apache-2.0
# -------------------------------- 𝒒𝒑𝒓𝒐𝒋 --

import 'just/shared.just'

mod ws 'just/ws.justfile'

_default:
    @just --justfile {{ justfile() }} --list --unsorted

# Lint GitHub Actions workflows.
actionlint:
    actionlint
