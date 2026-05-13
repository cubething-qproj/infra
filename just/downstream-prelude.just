# ------------------------------------------
# SPDX-License-Identifier: MIT OR Apache-2.0
# -------------------------------- 𝒒𝒑𝒓𝒐𝒋 --
#
# Downstream `justfile` prelude. NOT a standalone justfile -- the sync
# workflow concatenates this file with `shared.just` and writes the
# combined output as `justfile` in each downstream repo. This keeps the
# recipe definitions (in shared.just) as the single source of truth
# while letting downstreams ship a single justfile rather than a
# justfile + shared.just pair.
#
# `qproj` resolves to a `uvx --refresh` invocation that pulls the
# qproj-scripts CLI directly from the infra repo's `main` branch. The
# `--refresh` flag makes uvx re-resolve `main` to the current commit on
# every invocation; if the commit hasn't moved, the cached install is
# reused (no re-download).
#
# Override the ref by exporting `QPROJ_SCRIPTS_REF` (e.g. a commit SHA or
# branch name) -- useful for bisecting or temporarily holding a downstream
# back from upstream changes.

QPROJ_REF := env_var_or_default("QPROJ_SCRIPTS_REF", "main")
QPROJ_GIT_URL := "git+https://github.com/cubething-qproj/infra.git@" + QPROJ_REF + "#subdirectory=scripts"
qproj := "uvx --refresh --from " + quote(QPROJ_GIT_URL) + " qproj-scripts"
