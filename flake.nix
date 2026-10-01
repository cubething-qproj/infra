# ------------------------------------------
# SPDX-License-Identifier: MIT OR Apache-2.0
# -------------------------------- 𝒒𝒑𝒓𝒐𝒋 --
{
  description = "qproj - Bevy game utilities monorepo";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    rust-overlay = {
      url = "github:oxalica/rust-overlay";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  # GPU driver wrapping (formerly via nixGL inputs + a dedicated `nvidia`
  # devshell) is now handled ad-hoc in the `play` justfile recipe via
  # `nix run github:nix-community/nixGL#nixVulkan<Vendor>`. That keeps the
  # devshell pure (no `--impure`) and avoids paying nixGL's closure cost on
  # every shell entry -- you only pay it when you actually launch a binary.

  outputs = {
    self,
    nixpkgs,
    flake-utils,
    rust-overlay,
  }:
    flake-utils.lib.eachDefaultSystem (
      system: let
        overlays = [(import rust-overlay)];
        pkgs = import nixpkgs {inherit system overlays;};

        # The nightly date comes from the project template's rust-toolchain.toml,
        # which the sync copies downstream for local rustup builds. Only the
        # channel is read: each shell below picks its own components, which
        # keeps CI closures small.
        rustNightlyDate = pkgs.lib.removePrefix "nightly-" (builtins.fromTOML (
          builtins.readFile ./scripts/src/qproj_scripts/assets/project-template/rust-toolchain.toml
        )).toolchain.channel;

        mkRustToolchain = {
          profile ? "default",
          extensions,
          targets,
        }:
          (builtins.getAttr profile pkgs.rust-bin.nightly.${rustNightlyDate}).override {
            inherit extensions targets;
          };

        # The default profile includes rustdoc, local HTML documentation, and
        # rustfmt in addition to the explicitly requested developer tools.
        rustToolchainDev = mkRustToolchain {
          extensions = [
            "llvm-tools-preview"
            "clippy"
            "rust-analyzer"
            "rust-src"
          ];
          targets = [
            "x86_64-unknown-linux-gnu"
          ];
        };

        # Pipeline toolchain: minimal profile avoids rust-docs and rustfmt.
        # Clippy is required by the pipeline's Check step.
        rustToolchainCi = mkRustToolchain {
          profile = "minimal";
          extensions = [
            "clippy"
          ];
          targets = [
            "x86_64-unknown-linux-gnu"
          ];
        };

        # Coverage runs on a separate runner. It needs LLVM's instrumentation
        # tools, but not Clippy.
        rustToolchainCoverage = mkRustToolchain {
          profile = "minimal";
          extensions = [
            "llvm-tools-preview"
          ];
          targets = [
            "x86_64-unknown-linux-gnu"
          ];
        };


        linuxDeps = pkgs.lib.optionals pkgs.stdenv.hostPlatform.isLinux (with pkgs; [
          alsa-lib
          udev
          wayland
          libxkbcommon
          vulkan-loader
        ]);

        mkShell = {
          toolchain ? rustToolchainDev,
          extraPackages ? [],
          extraShellHook ? "",
        }:
          pkgs.mkShell {
            nativeBuildInputs = [pkgs.pkg-config];

            buildInputs = linuxDeps ++ [toolchain];

            packages = extraPackages;

            shellHook = ''
              export CARGO_TERM_COLOR="always"
              export PYTHONUNBUFFERED=1

              if [ -n "$SSH_CLIENT" ]; then
                export FEATURES=""
              else
                export FEATURES="dylib"
              fi

              if [ -f ".env.local" ]; then
                source ".env.local"
              fi

              ${extraShellHook}
            '';

            LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath linuxDeps;
          };

        # Packages used by `qproj-scripts build|test` and the pipeline's Check step.
        ciPackages = with pkgs; [
          sccache
          mold
          clang
          cargo-nextest
          uv
          python314
        ];

        coveragePackages = with pkgs; [
          mold
          clang
          cargo-nextest
          cargo-llvm-cov
        ];

        # Full developer toolbox.
        devPackages = with pkgs;
          ciPackages
          ++ [
            patchelf
            cargo-deny
            cargo-llvm-cov
            act
            actionlint
            just
          ];
      in {
        devShells.default = mkShell {extraPackages = devPackages;};
        devShells.ci = mkShell {
          toolchain = rustToolchainCi;
          extraPackages = ciPackages;
          extraShellHook = ''
            export CARGO_PROFILE_DEV_DEBUG=0
            export UV_PYTHON="${pkgs.python314}/bin/python3"
            export UV_PYTHON_DOWNLOADS=never
          '';
        };
        devShells.ci-coverage = mkShell {
          toolchain = rustToolchainCoverage;
          extraPackages = coveragePackages;
          extraShellHook = ''
            export CARGO_PROFILE_DEV_DEBUG=0
          '';
        };
      }
    );
}
