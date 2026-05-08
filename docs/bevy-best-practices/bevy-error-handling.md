# Bevy error handling

> Three-tier error model. 

This project handles errors in three distinct layers. Each layer has a
specific role; they're complementary, not substitutable.

---

## Layer 1 — Apps: top-level error handler

In any binary's top-level entry plugin (e.g., `quell::AppPlugin::build`),
register a fallback handler:

```rust
impl Plugin for AppPlugin {
    fn build(&self, app: &mut App) {
        app.set_error_handler(bevy::ecs::error::error);
        // ... rest of plugin setup
    }
}
```

The handler decides what happens to any system that returns
`Result<_, BevyError>` and errors. The default is to panic;
`bevy::ecs::error::error` logs the error at `error!` level and
continues.

**Analogy:** this is like `anyhow` in CLI/binary code — a single opaque
sink at the boundary that catches whatever bubbles up.

**Library plugins MUST NOT call `set_error_handler`.** Only the app
owns this decision.

---

## Layer 2 — Libraries: typed errors via `thiserror`

Public API and fallible systems return `Result<_, MyError>` where
`MyError` derives `thiserror::Error`:

```rust
#[derive(Error, Debug)]
pub enum ScreenError {
    #[error("Could not find screen {0}! Did you register it?")]
    NoSuchScreen(String),
    #[error("Could not find screen with ID {0:?}!")]
    NoSuchScreenId(ScreenId),
}
```

Already in place: `q_screens::ScreenError`. Extend the same pattern to
any new fallible API in `q_term`, `q_test_harness`, or future library
crates.

**Analogy:** this is like `thiserror` in library code — typed errors at
the boundary so callers can match on variants.

Fallible systems are written as `fn sys(...) -> Result<(), MyError>`
with `?`-propagation. They bubble to the app's Layer 1 handler when the
library is consumed by an app:

```rust
fn refresh_ui(
    terms: Query<&Terminal>,
    /* ... */
) -> Result<(), TermError> {
    for term in &terms {
        term.refresh()?;
    }
    Ok(())
}
```

---

## Layer 3 — Inline early-exit with `tiny_bail`

For **expected non-fatal misses** that don't merit a `Result`, use the
`tiny_bail` macros (re-exported from each crate's `prelude`):

```rust
use tiny_bail::prelude::*;

fn handle_switch_msg(
    mut reader: MessageReader<SwitchToScreenMsg>,
    mut current_screen: ResMut<CurrentScreen>,
    /* ... */
) {
    if reader.is_empty() {
        return;
    }
    let vec = reader.read().collect::<Vec<_>>();
    let msg_key = vec.iter().rev().find(|msg| /* ... */);
    let msg_key = rq!(msg_key); // return early if None, with a log
    // ... use msg_key
}
```

| Macro | Behavior on `None`/`Err` |
|---|---|
| `rq!(opt)` | log + return `()` |
| `cq!(opt)` | log + `continue` |
| `q!(opt)` | log + return `Default::default()` |
| `or_return!(opt, val)` | log + return `val` |

Use `tiny_bail` for:
- A query returning empty when emptiness is normal.
- An `Option` on a resource that's not yet initialized.
- A stale handle that was valid last frame.
- A `MessageReader` drained by a peer.

**Don't** use `tiny_bail` for:
- Asset load failures — those are unexpected; return `Result`.
- Invariant violations — those are bugs; return `Result` so the handler
  can log a real error.
- IO errors — return `Result`.

---

## Panicking

Use `unwrap()`, `expect()`, or `panic!` in a system or in
library code **only** when an implementation-level contract
is invalidated. These are equivalent to runtime assertions.

---

## Tests are a separate domain

`q_test_harness::CommandsExt::assert(condition, msg)` triggers
`commands.write_message(AppExit::error())` on failure. This is a
deliberate workaround for cross-thread panics not killing the test
process — see `q_test_harness/README.md` for the explanation.

Test code uses this pattern. **Library and binary code never use
`AppExit::error()` for assertion or error propagation.** That path is
test-domain-only.

There is an open spike on whether `panic = "abort"` could simplify
this. (TODO.)
