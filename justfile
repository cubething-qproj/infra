# ------------------------------------------
# SPDX-License-Identifier: MIT OR Apache-2.0
# -------------------------------- 𝒒𝒑𝒓𝒐𝒋 --

QPROJ_REF := env("QPROJ_SCRIPTS_REF", "main")
QPROJ_GIT_URL := "git+https://github.com/cubething-qproj/infra.git@" + QPROJ_REF + "#subdirectory=scripts"
SCRIPTS_SRC := env("QPROJ_SCRIPTS_SRC", QPROJ_GIT_URL)
qproj := "qproj-scripts"

_default:
    just --list

check:
    cd scripts && uv run ruff check
    cd scripts && uv run ruff format --check
    cd scripts && uv run basedpyright

test:
    cd scripts && uv run pytest -q

sync *args:
    {{ qproj }} sync {{ args }}

sync-scripts:
    uv tool install --force qproj-scripts --from {{ SCRIPTS_SRC }}

init *args:
    {{ qproj }} init {{ args }}
