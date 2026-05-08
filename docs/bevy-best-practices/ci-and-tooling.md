# CI and tooling

> `just` recipes, doc generation, test harness defaults.

---

## `just` is the canonical surface

All contributor and CI operations go through `just` recipes defined in
`infra/main/shared.just`. **Never invoke raw `cargo` for an operation
that has a recipe.** The recipes wrap project-specific arguments and
lint configuration that bare `cargo` won't apply.

### Recipe catalog

| Recipe | What it does |
|---|---|
| `just build [args]` | Build the workspace. Wraps `scripts/build.sh`. |
| `just play [args]` | Run the application (`quell`). |
| `just check [args]` | clippy + bevy_lint together. The default pre-commit check. |
| `just clippy [args]` | clippy alone. |
| `just bevy-lint [args]` | bevy_lint alone. |
| `just deny` | cargo-deny dependency audit. |
| `just test [args]` | Run tests via cargo-nextest. |
| `just coverage [args]` | Generate test coverage report. |
| `just fix [args]` | Apply clippy --fix. |
| `just ci [args]` | Run CI locally via `act`. |

The scripts these recipes wrap live in `infra/main/scripts/`. If you
need to extend a recipe, edit the script (in the `infra` worktree) —
not the recipe.

### Why not `cargo run -p ci` / xtask?

Bevy upstream uses `cargo run -p ci` (a binary crate at `tools/ci`).
Many ecosystem crates use xtask (`cargo run -p xtask -- <subcommand>`).
Both are functionally equivalent to `just` + shell scripts; xtask wins
when cross-platform Windows-without-WSL support is required.

We use `just` because:
- Recipes are more legible than Rust subcommand dispatch.
- Shell scripts are easier to inspect/modify than xtask source.
- We don't ship to Windows-without-WSL.

If that calculus changes, migrating `infra/main/scripts/` to an xtask
crate is straightforward — the recipes remain the contract.

---

## Documentation

### Library crates: `#![doc = include_str!("../README.md")]`

Every library crate's `lib.rs` opens with this attribute so the README
and the rustdoc front page are the same artifact:

```rust
#![doc = include_str!("../README.md")]
```

### Apps: inline `//!` rustdoc + `cfg(doc)` modules

`quell` is an app, not a library. It keeps its inline `//!` rustdoc
preamble and uses a `#[cfg(doc)] pub mod docs` module for
architecture-level prose:

```rust
// quell/src/lib.rs
#[cfg(doc)]
pub mod docs;
```

The `quell::docs` module is the canonical place for architecture and
pattern documentation that doesn't fit on a specific item. It compiles
only under rustdoc, so it has zero runtime cost.

### Doc-comment style (from Bevy upstream's guide)

- `///` doc comments belong **above** `#[derive(...)]` invocations.
- `//` for internal comments, generally above the line in question.
- Avoid `/* */` block comments.
- American English; capital letters; periods on sentence-like comments.
- Use `` `code` `` backticks for type/variable references.
- Doc-tests are run as part of the normal `cargo test` suite — don't
  let them rot.

### Examples count as integration tests

If a public API ships, it should have at least one minimal example
under `examples/` in the crate. Examples are CI-compiled, so they
double as integration tests against API drift.

---

## Test harness defaults

`q_test_harness::TestRunnerPlugin` ships these defaults:

| Field | Default | Why |
|---|---|---|
| `log_level` | `Level::TRACE` | Surface all debugging context in test output |
| `log_filter` | `DEFAULT_FILTER` | Standard Bevy filter |
| `executor_kind` | `ExecutorKind::SingleThreaded` | Avoids out-of-order errors and cross-thread panic loss |
| `TestRunnerTimeout` | `5.0` seconds | Forgiving for slow CI runners |
| `LogTestSteps` | `true` | Log step counts during test execution |

Downstream test code overrides via plugin construction:

```rust
app.add_plugins(TestRunnerPlugin {
    log_level: Level::INFO,
    log_filter: "wgpu=warn,my_crate=trace".into(),
    executor_kind: ExecutorKind::Simple,
});
```

### Two test patterns supported

**Pattern 1 — manual update style.** Explicit `app.update()` calls
between assertions:

```rust
let mut app = test_app();
app.update();
assert_eq!(app.world().resource::<Foo>().value, 42);
```

**Pattern 2 — run-to-exit style.** Use
`commands.write_message(AppExit::Success)` /
`commands.write_message(AppExit::error())` from within `PostUpdate`
chained systems. **In pattern 2 you cannot use `assert!` macros**
because Bevy systems run on separate threads and panicking won't kill
the test process — only the worker thread. Use
`q_test_harness::CommandsExt::assert(condition, msg)` instead, which
writes `AppExit::error()` on failure.

See `q_test_harness/README.md` for the full explanation of why pattern
2 needs the indirection. There is an open spike on whether
`panic = "abort"` would simplify this. (TODO.)

---

## CI invocation

CI runs the same `just` recipes as local development. Verify that the
GitHub Actions (or equivalent) workflow files invoke `just check`,
`just test`, `just deny` — not raw cargo. If they don't, fix the
workflow, not the recipes.

Local CI dry-run: `just ci` (uses `act`).
