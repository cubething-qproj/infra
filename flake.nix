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
    # bevy_cli ships its own flake exposing a `bevy` package whose
    # binary includes the `lint` subcommand (which in turn dispatches to
    # bevy_lint_driver). Consuming it directly removes the need to vendor
    # the bevy_cli source and rebuild bevy_lint from scratch via crane.
    bevy_cli.url = "github:TheBevyFlock/bevy_cli";
    # nixGL: wraps binaries so Nix-linked Vulkan/GL apps can find host
    # GPU drivers on non-NixOS hosts. Required because Nix's glibc loader
    # ignores /etc/ld.so.cache, so system ICDs' bare-name dlopen() fails.
    nixgl = {
      url = "github:nix-community/nixGL";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.flake-utils.follows = "flake-utils";
    };
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
    rust-overlay,
    bevy_cli,
    nixgl,
  }:
    flake-utils.lib.eachDefaultSystem (
      system: let
        overlays = [(import rust-overlay)];
        pkgs = import nixpkgs {inherit system overlays;};

        # Keep in sync with bevy_cli's rust-toolchain.toml. The
        # upstream flake's `bevy_lint_driver` is built against this exact
        # nightly; running it under any other rustc ABI fails to load.
        rustToolchain = pkgs.rust-bin.nightly."2026-03-05".default.override {
          extensions = [
            "rustc-codegen-cranelift-preview"
            "rustc-dev"
            "llvm-tools-preview"
            "clippy"
            "rust-analyzer"
            "rust-src"
          ];
          targets = [
            "x86_64-pc-windows-msvc"
            "x86_64-unknown-linux-gnu"
          ];
        };

        # The `bevy` CLI from the upstream flake. `bevy lint` is the
        # entry point; the package bundles the lint driver alongside it.
        bevy-cli = bevy_cli.packages.${system}.default;

        linuxDeps = pkgs.lib.optionals pkgs.stdenv.isLinux (with pkgs; [
          alsa-lib
          udev
          wayland
          libxkbcommon
          vulkan-loader
        ]);

        # Mesa wrapper covers AMD, Intel, and Nouveau (purely buildable).
        # nixGLNvidia uses builtins.exec to read the host driver version and
        # therefore requires `nix develop --impure` (plus
        # allow-unsafe-native-code-during-evaluation). It is offered via a
        # separate `nvidia` devshell so mesa users don't pay that cost.
        nixglPkgs = pkgs.lib.optionals pkgs.stdenv.isLinux [
          nixgl.packages.${system}.nixVulkanIntel
        ];

        nixglNvidiaPkgs = pkgs.lib.optionals pkgs.stdenv.isLinux [
          nixgl.packages.${system}.nixVulkanNvidia
        ];

        mkShell = extraPackages:
          pkgs.mkShell {
            nativeBuildInputs = [pkgs.pkg-config];

            buildInputs =
              linuxDeps
              ++ [
                rustToolchain
                bevy-cli
              ];

            packages =
              (with pkgs; [
                sccache
                mold
                patchelf
                cargo-nextest
                cargo-deny
                cargo-llvm-cov
                act
                actionlint
                just
                uv
              ])
              ++ extraPackages;

            shellHook = ''
              export CARGO_TERM_COLOR="always"
              export PYTHONUNBUFFERED=1
              export RUSTC_WRAPPER="sccache"

              if [ -n "$SSH_CLIENT" ]; then
                export FEATURES=""
              else
                export FEATURES="dylib"
              fi

              if [ -f ".env.local" ]; then
                source ".env.local"
              fi
            '';

            LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath linuxDeps;
          };
      in {
        devShells.default = mkShell nixglPkgs;
        # Use with: `nix develop --impure .#nvidia` (or in .envrc:
        # `use flake --impure .#nvidia`).
        devShells.nvidia = mkShell nixglNvidiaPkgs;
      }
    );
}
