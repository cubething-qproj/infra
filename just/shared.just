# ------------------------------------------
# SPDX-License-Identifier: MIT OR Apache-2.0
# -------------------------------- 𝒒𝒑𝒓𝒐𝒋 --
#
# Recipes that wrap the qproj-scripts CLI. Consumers of this file
# (metarepo.just, downstream.just) must define `qproj` themselves --
# typically as `uv run --project <local-scripts>` for the metarepo and
# `uvx --from git+...` for downstreams.

# Build the workspace.
build *args:
    {{ qproj }} build {{ args }}

# Run the application.
play *args:
    {{ qproj }} play {{ args }}

# Lint with Clippy and bevy_lint.
check *args:
    {{ qproj }} check {{ args }}

# Run clippy.
clippy *args:
    {{ qproj }} clippy {{ args }}

# Run bevy_lint.
bevy-lint *args:
    {{ qproj }} bevy-lint {{ args }}

# Check dependencies with cargo-deny.
deny:
    {{ qproj }} deny

# Run tests via cargo-nextest.
test *args:
    {{ qproj }} test {{ args }}

# Generate test coverage report.
coverage *args:
    {{ qproj }} coverage {{ args }}

# Fix all fixable issues.
fix *args:
    {{ qproj }} fix {{ args }}

# Test CI locally with act.
ci *args:
    {{ qproj }} ci {{ args }}

# Emit Clippy + bevy_lint diagnostics as JSON for rust-analyzer.
ra-check *args:
    {{ qproj }} ra-check {{ args }}
