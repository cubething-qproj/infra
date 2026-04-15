#!/usr/bin/env bash
set -euo pipefail
RUSTC_WRAPPER="" bevy_lint \
	--all-features \
	--target-dir=target/bevy_lint "$@"
