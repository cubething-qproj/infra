#!/usr/bin/env bash
# Runs clippy and bevy_lint, merging their JSON diagnostics for rust-analyzer.
set -uo pipefail

cargo clippy --all-features \
    --target-dir=target/ra-clippy \
    --message-format=json-diagnostic-rendered-ansi "$@" 2>/dev/null

RUSTC_WRAPPER="" bevy_lint --all-features \
    --target-dir=target/ra-bevy-lint \
    --message-format=json-diagnostic-rendered-ansi "$@" 2>/dev/null
