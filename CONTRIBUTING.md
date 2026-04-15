# Contributing to qproj

Thanks for your interest! This document covers everything you need to work on
this project — setup, building, testing, code style, and conventions.

## Overview

qproj is a Rust monorepo for [Bevy](https://bevy.org) game utilities. The
crates are tightly coupled and share build tooling, so they live together.

### Repository layout

```
qproj/
├── workspace/           # Cargo workspace root
│   ├── Cargo.toml       # Workspace manifest (members = ["crates/*"])
│   ├── Cargo.lock
│   ├── assets/
│   └── crates/
│       ├── app/             # Main game application
│       ├── screens/         # q_screens — screen management plugin
│       ├── term/            # q_term — in-game terminal plugin
│       └── test_harness/    # q_test_harness — shared test utilities
├── submod/bevy          # Bevy git submodule (reference only)
├── flake.nix            # Nix flake (dev shell, tools, bevy_lint)
├── justfile             # Task runner recipes
├── scripts/             # Task scripts invoked by justfile
├── .envrc               # direnv integration
├── .config/
│   └── nextest.toml     # Test runner config
├── .cargo/config.toml   # Cargo build settings (cranelift, mold)
├── deny.toml            # cargo-deny dependency policy
└── .github/workflows/   # CI definitions
```

All Cargo commands should target `workspace/Cargo.toml`, e.g.
`cargo build --manifest-path=./workspace/Cargo.toml`. The justfile recipes
handle this automatically.

## Setup

Install [Nix](https://nixos.org/download/) and
[direnv](https://direnv.net/docs/installation.html), then:

```sh
git clone --recurse-submodules https://github.com/ada-x64/qproj.git
cd qproj
direnv allow     # Activates the Nix dev shell automatically
just             # Lists all available tasks
```

Alternatively, without direnv:

```sh
nix develop      # Enter the dev shell manually
just             # Lists all available tasks
```

The Nix dev shell provides the full toolchain:

- **Rust nightly-2026-01-22** with cranelift, llvm-tools, and clippy
- **sccache** for compilation caching
- **mold** linker (Linux)
- **bevy_lint** (built from source)
- **cargo-nextest**, **cargo-deny**, **cargo-llvm-cov**
- **just** task runner

### System dependencies (Linux)

```sh
sudo apt-get install -y libasound2-dev libudev-dev libwayland-dev
```

## Building and running

| Command        | Description                              |
| -------------- | ---------------------------------------- |
| `just build`   | Build the workspace                      |
| `just play`    | Run the application                      |
| `just check`   | Lint with Clippy and bevy_lint           |
| `just deny`    | Check dependencies with cargo-deny       |
| `just test`    | Run tests via cargo-nextest              |
| `just coverage` | Generate test coverage report           |
| `just ci`      | Run CI locally with [act](https://github.com/nektos/act) |

You can pass arguments through to the underlying tools. For example:

```sh
just test r -p q_term              # Test a specific package
just build --release               # Release build
just clippy -p q_screens           # Lint a specific package
```

## Testing

Tests use [cargo-nextest](https://github.com/nextest-rs/nextest). Coverage is
generated with [cargo-llvm-cov](https://github.com/taiki-e/cargo-llvm-cov).
The default test timeout is 1 second with termination after 3 retries (see
`.config/nextest.toml`).

### Test harness

Tests should use
[q_test_harness](./workspace/crates/test_harness/README.md) to set up a
headless Bevy `App` with the right plugins and a configurable runner. See that
crate's documentation for patterns and examples.

Each crate that uses `q_test_harness` typically defines a local `test` module
in `lib.rs` that configures the harness with the crate's own plugin:

```rust
#[cfg(test)]
mod test {
    use crate::prelude::*;
    pub use q_test_harness::prelude::*;

    pub fn test_harness(app: &mut App) {
        app.add_plugins(TestRunnerPlugin::default());
        app.add_plugins(MyCratePlugin);
        app.insert_resource(TestRunnerTimeout(1.));
    }
}
```

### Running CI locally

```sh
just ci
# Or target a specific workflow/matrix:
just ci -W ./.github/workflows/ci.yml --matrix target:x86_64-unknown-linux-gnu
```

## Code style

### Conventions

- **Rust 2024 edition.** All crates use `edition = "2024"`.
- **Prelude pattern.** Each crate re-exports its public API through a
  `prelude` module. Internal imports use `pub(crate) use bevy::prelude::*`.
- **Documentation.** Public-facing crates should use `#![deny(missing_docs)]`.
- **Error handling.** Use `tiny_bail` for fallible Bevy systems and `thiserror`
  for typed errors.
- **Workspace lints.** Configured in `workspace/Cargo.toml` under
  `[workspace.lints]`. All crates inherit these with `[lints] workspace = true`.

### What the linters check

CI runs both `clippy` and `bevy_lint`. Make sure both pass before submitting:

```sh
just check
```

### Build profiles

| Profile       | Use case                        |
| ------------- | ------------------------------- |
| `dev`         | Local development (cranelift)   |
| `release`     | Optimized for size, stripped    |
| `dist`        | Distribution (max optimization) |
| `wasm-dev`    | WebAssembly development         |
| `server-dev`  | Server/headless development     |
| `android-dev` | Android development             |

Dev builds use the **cranelift** codegen backend and the **mold** linker for
fast iteration. Dependencies are built at `opt-level = 3` even in dev.

## PRs and commit messages

PRs are squash-merged into a single commit using
[Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) format.
This powers automatic changelog generation.

Examples:

```
feat(screens): add transition animations
fix(term): correct line wrapping on resize
refactor: simplify test harness setup
```

All CI checks must pass. If you authored a PR using an LLM, please disclose
that.

## Publishing

Crates are published with
[cargo-smart-release](https://github.com/crate-ci/cargo-release). Aim for at
least 80% test coverage before release. Contributors generally don't need to
worry about this step.

## Compatibility

| Branch/tag | Bevy |
| ---------- | ---- |
| main       | 0.18 |
