# Workspace conventions

> `Cargo.toml` shape, lint config, feature flags, build profiles,
> toolchain pin. 


---

## Toolchain

This workspace uses **nightly Rust**, pinned to whatever `bevy_lint`
requires (currently `nightly-2026-01-22`). Updated when `bevy_lint`
updates. Pinned via `rust-toolchain.toml` at the metarepo root.

There is **no MSRV** (`rust-version` is not declared). MSRV is
meaningless under a nightly pin.

`quell` and `q_screens` use:

```rust
#![feature(register_tool)]
#![register_tool(bevy)]
#![allow(bevy::panicking_methods)]
```

This is intentional — `register_tool(bevy)` enables `bevy_lint`
attributes on stable-shaped code. Crates that participate in
`bevy_lint` declare these inner attributes; crates that don't can omit
them.

---

## Workspace `[lints]` table

Every crate sets `[lints] workspace = true` to inherit. Crate-level
overrides require a documented reason.

The workspace lint table:

```toml
[workspace.lints.rust]
missing_docs = "warn"
unsafe_op_in_unsafe_fn = "warn"
unused_qualifications = "warn"
unsafe_code = "deny"
unexpected_cfgs = { level = "warn", check-cfg = ["cfg(bevy_lint)"] }

[workspace.lints.clippy]
# Warned
doc_markdown = "warn"
nonstandard_macro_braces = "warn"
print_stdout = "warn"
print_stderr = "warn"
redundant_closure_for_method_calls = "warn"
semicolon_if_nothing_returned = "warn"
undocumented_unsafe_blocks = "warn"
manual_let_else = "warn"
match_same_arms = "warn"
redundant_else = "warn"
allow_attributes = "warn"
allow_attributes_without_reason = "warn"

# Allowed (Bevy ergonomics)
type_complexity = "allow"
too_many_arguments = "allow"
needless_lifetimes = "allow"
too_long_first_doc_paragraph = "allow"
```

**Goal**: every public API documented (`missing_docs` warn) and every
`allow` attribute justified (`allow_attributes_without_reason` warn).

**Dropped from Bevy upstream's set**: `std_instead_of_core`,
`std_instead_of_alloc`, `alloc_instead_of_core` — we are not pursuing
`no_std`.

`type_complexity` and `too_many_arguments` are allowed because Bevy's
DI naturally produces both.

### Per-crate overrides

If a crate genuinely needs unsafe (e.g., `q_screens`'s manual
`SystemParam` impls), override at the crate level:

```toml
[lints.rust]
unsafe_code = "allow"
```

with a reason in the `Cargo.toml` comment block.

---

## Imports and the prelude pattern

Every crate exports a project-local `pub mod prelude { ... }`.
Submodules use `use crate::prelude::*;`. External consumers use
`use <crate>::prelude::*;`.

This **intentionally diverges from Bevy upstream's** "prefer granular
imports" contributor rule. cubething-qproj is shaped like an ecosystem
library set, not like Bevy itself; consumers (including our own app
crate) benefit more from a curated prelude than from spelling out every
type.

Build-time impact is presumed negligible.

---

## Cargo features

### `dev` — every crate with dev tooling exposes it

Gates: debug overlays, inspector wiring, `bevy_mod_debugdump`,
`bevy/file_watcher`, `bevy/bevy_dev_tools`, any
`#[cfg(feature = "dev")]` modules.

```toml
[features]
dev = ["dep:bevy_mod_debugdump"]
```

- Apps build with `--features dev` during development; omit in release.
- `dev` is **never** a default feature.
- Library crates with no dev tooling MAY omit `dev`.

### `dylib` — every Bevy-dependent crate exposes it

Gates `bevy/dynamic_linking` (and `dep:bevy_dylib` where applicable):

```toml
[features]
dylib = ["bevy/dynamic_linking"]
```

- Speeds up incremental compilation during development.
- **Never** a default feature.
- Applied uniformly across `quell`, `q_term`, `q_screens`,
  `q_test_harness` (and any future Bevy-dependent crate).

### Application-specific features

`quell` may have additional features (e.g., `dev` gates the clap CLI).
Document them in the crate's `Cargo.toml` and README.

### Mutually exclusive features

If you ever introduce them (e.g., `f32`/`f64` à la avian), enforce with
`compile_error!` blocks in the crate's `lib.rs`:

```rust
#[cfg(all(feature = "f32", feature = "f64"))]
compile_error!("Cannot enable both `f32` and `f64` features");
```

---

## Build profiles

Three profiles, codified at the workspace level:

```toml
[profile.dev]
opt-level = 1
[profile.dev.package."*"]
opt-level = 3

[profile.release]
opt-level = "s"
lto = true
codegen-units = 1
strip = true

[profile.dist]
inherits = "release"
opt-level = 3
lto = true
codegen-units = 1
strip = true
```

| Profile | Use |
|---|---|
| `dev` | Fast iteration. Dependencies built optimised; user code at `opt-level = 1`. |
| `release` | Default ship target. Size-optimised. |
| `dist` | Speed-optimised distribution artifact. |

### Pruned profiles

`wasm-dev`, `server-dev`, `android-dev` were removed. Targets are
native and wasm only (game-jam projects). Per-target overrides go in
`.cargo/config.toml` under `[target.<triple>]` rather than via profile
proliferation.

### `panic = "abort"` is deferred

Pending a spike to verify it doesn't break `q_test_harness`
cross-thread panic semantics or `#[should_panic]` tests. (TODO.)

---

## Per-crate `[dependencies]` conventions

### `bevy-inspector-egui` is dev-only

Move from regular dep to `[dev-dependencies]` everywhere it's used. It
pulls in egui, bevy_egui, and accessibility/winit machinery; never
ships in release.

`q_screens` already places it correctly. `quell` and `q_term` need to
move it.

A future-work item exists to factor out the small subset of
`bevy-inspector-egui` types `q_screens` actually uses, into either a
fork or a small in-tree crate. (TODO.)

### Workspace-wide deps

Pin Bevy and major ecosystem deps **per-crate**, not at the workspace
level. This makes per-crate version skew during a Bevy migration
explicit (see [`bevy-versioning.md`](bevy-versioning.md)).

---

## `Cargo.toml` skeleton for a new crate

```toml
[package]
name = "q_newcrate"
version = "0.1.0"
edition = "2024"
license = "MIT OR Apache-2.0"
repository = "https://github.com/cubething-qproj/q_newcrate"
description = "..."

[package.metadata.bevy_lint]
panicking_methods = { level = "warn" }

[lints]
workspace = true

[dependencies]
bevy = "0.18"
tiny_bail = "0.7"
thiserror = "2"
# ...

[features]
dev = []
dylib = ["bevy/dynamic_linking"]
```

And in `lib.rs`:

```rust
#![doc = include_str!("../README.md")]
#![feature(register_tool)]
#![register_tool(bevy)]
#![allow(bevy::panicking_methods, reason = "transitional, prefer Result")]

mod data;
mod plugin;
mod systems;

pub mod prelude {
    pub use super::data::*;
    pub use super::plugin::*;
    pub(crate) use bevy::prelude::*;
    pub(crate) use tiny_bail::prelude::*;
}
```
