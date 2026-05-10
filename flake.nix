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
    crane.url = "github:ipetkov/crane";
    bevy-cli-src = {
      url = "github:TheBevyFlock/bevy_cli/lint-v0.6.0";
      flake = false;
    };
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
    crane,
    bevy-cli-src,
    nixgl,
  }:
    flake-utils.lib.eachDefaultSystem (
      system: let
        overlays = [(import rust-overlay)];
        pkgs = import nixpkgs {inherit system overlays;};

        # Keep in sync with bevy_cli
        rustToolchain = pkgs.rust-bin.nightly."2026-01-22".default.override {
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

        craneLib = (crane.mkLib pkgs).overrideToolchain rustToolchain;

        # bevy_lint — rustc driver built from the bevy_cli repository.
        # Must use the exact same nightly toolchain since it links
        # against rustc internals via #![feature(rustc_private)].
        bevy_lint = craneLib.buildPackage {
          src = bevy-cli-src;
          pname = "bevy_lint";
          version = "0.6.0";
          cargoExtraArgs = "-p bevy_lint";
          doCheck = false;

          LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [rustToolchain pkgs.zlib];
          nativeBuildInputs = [pkgs.makeWrapper];

          postInstall = ''
            for bin in $out/bin/bevy_lint $out/bin/bevy_lint_driver; do
              [ -f "$bin" ] && wrapProgram "$bin" \
                --prefix LD_LIBRARY_PATH : "${pkgs.lib.makeLibraryPath [rustToolchain pkgs.zlib]}"
            done
          '';
        };

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
                bevy_lint
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
