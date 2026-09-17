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

update-flake:
    #!/usr/bin/env bash
    set -euo pipefail

    nix flake update

    sccache_version="$(nix eval --raw --impure --expr '
      let
        flake = builtins.getFlake (toString ./.);
        pkgs = import flake.inputs.nixpkgs {
          system = builtins.currentSystem;
          overlays = [ (import flake.inputs.rust-overlay) ];
        };
      in pkgs.sccache.version
    ')"
    rust_toolchain="$(nix eval --raw --impure --expr '
      let
        flake = builtins.getFlake (toString ./.);
        toolchain = builtins.fromTOML (
          builtins.readFile "${flake.inputs.bevy_cli}/rust-toolchain.toml"
        );
      in toolchain.toolchain.channel
    ')"
    rust_nightly="${rust_toolchain#nightly-}"

    setup_action=.github/actions/setup/action.yml
    [[ $(grep -Ec '^[[:space:]]*version: "v[0-9]+\.[0-9]+\.[0-9]+"$' "$setup_action") -eq 1 ]]
    sed -i.bak -E \
      "s/(version: \"v)[0-9]+\.[0-9]+\.[0-9]+/\\1${sccache_version}/" \
      "$setup_action"

    [[ $rust_toolchain == nightly-[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] ]]
    [[ $(grep -Ec 'rust-bin\.nightly\."[0-9]{4}-[0-9]{2}-[0-9]{2}"' flake.nix) -eq 1 ]]
    sed -i.bak -E \
      "s/(rust-bin\.nightly\.\")[0-9]{4}-[0-9]{2}-[0-9]{2}/\\1${rust_nightly}/" \
      flake.nix

    rm -f "$setup_action.bak" flake.nix.bak

init *args:
    {{ qproj }} init {{ args }}
