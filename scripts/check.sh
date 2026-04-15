#!/usr/bin/env bash
set -euo pipefail
PKG=""
if [[ "${1:-}" != "" ]]; then PKG="-p $1"; fi
scripts/clippy.sh $PKG &
scripts/bevy-lint.sh $PKG &
wait
