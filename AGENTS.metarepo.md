# AGENTS.md — cubething-qproj metarepo

This is the always-on context for agents working in this repo. Rules here
apply to **every** code-touching action. Reference material lives under
[`infra/main/docs/bevy-best-practices/`](infra/main/docs/bevy-best-practices/) and is fetched
on-demand when a relevant tool call happens.

> **Note on this file's lifecycle.** `AGENTS.md` at the metarepo root is
> seeded once by `infra/main/setup.sh` from `infra/main/AGENTS.metarepo.md`
> on a clean checkout, then left alone. Unlike `justfile` (which has
> `just self-update` to re-copy from `infra/main/metarepo.just`), there is
> **no** refresh recipe for `AGENTS.md` — once seeded, the file is
> operator-owned. To pick up template improvements, run
> `diff -u AGENTS.md infra/main/AGENTS.metarepo.md` from the metarepo root
> and merge selected hunks by hand.

---

## Repo shape

This is a **metarepo**. The root `Cargo.toml` is symlinked to the `infra`
repo, which holds workspace infrastructure. Every other top-level directory
is its own Rust crate, checked out as a **bare + worktree** layout:

```
crate_name/
  bare/          # bare git clone
  main/          # always-checked-out worktree of origin/main
  feat/<name>/   # feature worktrees
  fix/<name>/    # fix worktrees
  active -> main # symlink, points at the worktree the workspace uses
```

Workspace members are `quell/active`, `q_term/active`, `q_screens/active`,
`q_test_harness/active` — all symlinks into per-crate worktrees.

### Before starting work

1. **Ask the operator if you should use a new worktree.** This is
   important. Do not work directly in `active/` (which is `main/`) without
   confirmation.
2. **Fetch latest.** Base your changes on `origin/main` unless told
   otherwise.
3. **Branch convention** (inside any per-crate worktree):
   ```
   main/                              # always present
   feat/<change>                      # features
   feat/<initiative>/<sub-aspect>     # multi-PR initiatives
   fix/<change>                       # fixes
   docs/<change>                      # docs-only
   ci/<change>                        # CI-only
   tests/<change>                     # test-only
   ```

### Workspace manipulation (`just ws`)

All cross-repo workspace operations go through `just ws <recipe>`,
which wraps the `pj` scripts under `infra/main/pj/scripts/`.

| Recipe | What it does |
|---|---|
| `just ws wt add <repo> <branch>` | Create a worktree on `<branch>` in `<repo>` and repoint `<repo>/active` to it. Creates the branch from current `active` HEAD if it doesn't exist. Add `--no-switch` to leave `active` alone. |
| `just ws wt switch <repo> <wt>` | Repoint `<repo>/active` to an existing worktree. This is **the** way to retarget `active`. Never `ln -sf` it by hand. |
| `just ws wt rm <repo> <branch>` | Remove a worktree. Refuses `main` / current `active`. |
| `just ws wt ls [repo]` | List worktrees (all repos if no arg). |
| `just ws wt status` | Show the current `active` symlink target for every repo. |
| `just ws doctor` | Workspace health-check across primary repos. |
| `just ws clean` | Clean stale worktrees / branches across primary repos. |
| `just ws install-git` | Install shared git hooks into primary repos. |
| `just ws venv <args>` | Point basedpyright at a Python interpreter (venv dir or python binary). |
| `just self-update` | Regenerate the metarepo justfile from the `infra` template. |

**When the operator says "use a new worktree for this":**

```sh
just ws wt add <repo> <branch>   # creates + switches active to it
cd <repo>/active                  # now on the new worktree
```

**When done with a worktree:**

```sh
just ws wt switch <repo> main    # repoint active back to main
just ws wt rm <repo> <branch>    # delete the worktree
```

---

## Bevy code conventions (always-on)

These are the rules an agent needs every time it touches Rust/Bevy code in
this repo. Scope-specific reference material is linked at the bottom.

### Plugin shape

- **Application internals** (submodules of an app or library crate):
  use `pub(super) fn plugin(app: &mut App)` and register with
  `app.add_plugins(submodule::plugin)`.
- **Library public exports** and the **app's top-level entry plugin**:
  use `pub struct XPlugin; impl Plugin for XPlugin`. Stable struct
  identity protects SemVer when configuration is added later.
- **One plugin per file.** Omit plugins that would be empty.
- A library plugin that adds systems to a shared schedule (`Update`,
  `FixedUpdate`, `PostUpdate`, etc.) **must** publish a public
  `#[derive(SystemSet)]` enum and register all its systems
  `.in_set(ThatSet)`. Multi-schedule plugins may publish multiple sets.
- A library plugin that owns a phase of the frame **must** offer
  `Plugin::new(schedule: impl ScheduleLabel)` alongside
  `Plugin::default()`. Hardcoded schedules in library code are not
  acceptable.
- For multi-plugin libraries (>2 plugins routinely shipped together),
  export a `pub struct FooPlugins; impl PluginGroup`.

### Module shape

- **No mandatory skeleton.** Start with a single `lib.rs` (flat library
  crate) or `mod.rs` (subsystem). Split into a directory when
  complexity creates friction. We recommend using the skeleton anyways.
- When splitting, the canonical concern axes are: `data.rs` (components,
  resources, states, markers), `systems.rs`, `messages.rs`,
  `observers.rs`, `bundle.rs` (prefab-shaped
  game-state factories only — not for trivial spawns), `state.rs`
  (`#[derive(States)]` enums when they merit isolation), `mod.rs` /
  `lib.rs` exports `pub(super) fn plugin` plus the local `prelude`.

### Bundles, observers, startup

- **Bundles**: `#[derive(Bundle)] struct FooBundle { ... }` for simple
  amalgams of components. `fn foo(...) -> impl Bundle` when construction
  takes parameters or composes via `children![ ... ]`. `bundle.rs` is
  not a default file in the skeleton; it appears only where the crate
  has actual prefab-shaped entities.
- **Observers as spawn hooks**: when a marker component is inserted, run
  setup via `app.add_observer(setup_foo)` with `setup_foo(add: On<Add,
  Foo>, ...)`. Prefer this over `Startup` systems for entity setup.
- **`Startup` is for long-lived singletons only**: top-level cameras,
  root UI containers, persistent global resources. Lazy initialization
  is preferred wherever possible.

### Imports

- **Project-local prelude is canonical.** Inside a crate, submodules use
  `use crate::prelude::*;`. External consumers use
  `use <crate>::prelude::*;`. Granular imports only to resolve
  ambiguity.
- This intentionally diverges from Bevy upstream's contributor rule
  ("prefer granular imports"). cubething-qproj is library-shaped, not
  Bevy-internal-shaped. See
  [`infra/main/docs/bevy-best-practices/workspace-conventions.md`](infra/main/docs/bevy-best-practices/workspace-conventions.md).

### Errors

Three-tier model:

- **Apps (binaries)**: top-level entry plugin calls
  `app.set_error_handler(...)` (renamed `set_fallback_error_handler` in
  0.19). Logs and continues; never panic.
- **Libraries**: declare typed errors with `thiserror::Error`. Public
  API and fallible systems return `Result<_, MyError>`. Already in
  place: `q_screens::ScreenError`.
- **Inline early-exit**: `tiny_bail::prelude` (`rq!`, `cq!`, etc.) for
  expected non-fatal misses (empty queries, stale handles, not-yet-
  initialized resources). Does not produce a `Result`.
- **Panics are allowed only for invalidated implementation-level
  contracts** — i.e. runtime assertions. Don't use `unwrap()` /
  `expect()` / `panic!` for ordinary fallibility; that's what `Result`
  and `tiny_bail` are for.
- The `bevy_lint::panicking_methods` lint catches a narrower thing
  than its name suggests: it flags calls to *Bevy's own* panicking
  method variants where a non-panicking variant exists
  (e.g. `Query::single()` vs `Query::get_single()`, certain direct
  `World` mutations). It does **not** flag `unwrap()` / `expect()` /
  `panic!` in your own code.
- **Test code is a separate domain.** Use
  `q_test_harness::CommandsExt::assert(...)` which writes
  `AppExit::error()`. Production code never uses `AppExit::error()` for
  assertion. (TODO: Spike on panic=abort to test if this is a required
  pattern.)

### Documentation

- Every `pub` item carries a rustdoc comment. `missing_docs` is warned
  at the workspace level.
- Library crates open `lib.rs` with
  `#![doc = include_str!("../README.md")]` so README and rustdoc front
  page are the same artifact.
- `///` comments above `#[derive(...)]`. American English. Capitals.
  Periods on sentence-like comments. No `/* */` blocks.

### Bevy version

Workspace targets **Bevy 0.18**. Migration to 0.19 is gated on the
ecosystem catching up; see
[`infra/main/docs/bevy-best-practices/bevy-versioning.md`](infra/main/docs/bevy-best-practices/bevy-versioning.md).

### Tooling

Use `just` recipes for everything. Never tell a contributor (or yourself)
to invoke raw `cargo` for an operation that has a recipe. Full catalog
in [`infra/main/docs/bevy-best-practices/ci-and-tooling.md`](infra/main/docs/bevy-best-practices/ci-and-tooling.md).

Common ones:
- `just check` — clippy + bevy_lint
- `just test` — nextest
- `just play` — run the app
- `just fix` — clippy --fix

### Toolchain

This workspace uses **nightly Rust**, pinned to whatever `bevy_lint`
requires. `quell` and `q_screens` use `#![feature(register_tool)]
#![register_tool(bevy)]` to enable `bevy_lint`. There is no MSRV.

---

## When to read what (reference material)

Fetch these on-demand based on what you're touching:

| Touching... | Read... |
|---|---|
| Any `Cargo.toml` | [`infra/main/docs/bevy-best-practices/workspace-conventions.md`](infra/main/docs/bevy-best-practices/workspace-conventions.md) |
| Plugin / system / module structure | [`infra/main/docs/bevy-best-practices/bevy-conventions.md`](infra/main/docs/bevy-best-practices/bevy-conventions.md) |
| Anything that returns `Result` or uses `tiny_bail` | [`infra/main/docs/bevy-best-practices/bevy-error-handling.md`](infra/main/docs/bevy-best-practices/bevy-error-handling.md) |
| Bumping a Bevy-related dep | [`infra/main/docs/bevy-best-practices/bevy-versioning.md`](infra/main/docs/bevy-best-practices/bevy-versioning.md) |
| `q_screens` internals or its consumers | the `q_screens` crate's own rustdoc (`cargo doc -p q_screens --open`) |
| `justfile`, scripts, CI configs | [`infra/main/docs/bevy-best-practices/ci-and-tooling.md`](infra/main/docs/bevy-best-practices/ci-and-tooling.md) |

For human-facing onboarding, see [`infra/main/CONTRIBUTING.md`](infra/main/CONTRIBUTING.md).

---

## Pre-design synthesis flow

(Process documentation, used when the operator initiates a synthesis pass
on a `research.md` artifact.)

**Preconditions:**
- A `research.md` exists for the topic (wide survey, prior art, tensions,
  open questions).
- The operator is already saturated in the domain — has positions to
  test, not to derive.
- Operator commits to active in-the-loop participation (not executor-
  style delegation).

**Loop** (one pass per source):

1. Agent surfaces the next resource — one at a time, no batching unless
   the operator explicitly asks to consolidate.
2. Agent provokes: states what this source claims, what tension it
   introduces, what it would force the operator to commit to or reject.
3. Operator responds — confirms, complicates, or restates a prior
   position.
4. Agent synthesizes the exchange into the appropriate section of the
   append-only `pre-design-decisions.md`:
    - **Decision** — committed; downstream design inherits it. Cites
      source.
    - **Principle** — operator-ratified belief grounding future
      decisions. Cites source.
    - **Open question** — design-phase question; options narrowed but
      not picked.
    - **ORQ** — outstanding research question; outside d3r's design
      scope, bounds what we can claim.
5. Agent adds a column for this source to the running cross-source
   comparison table.
6. Operator catches miscites; agent surfaces tensions operator hadn't
   named. Drift gets corrected in-place, not by revising history.

**Termination**: all sources walked, comparison table complete, open
questions and ORQs consolidated, suggested design-phase tackling order
written.

**Output**: `pre-design-decisions.md` — append-only, four-section
taxonomy + comparison table, every Decision/Principle traced to a source.

**Refusal conditions**:
- No `research.md` → this is research, not synthesis.
- Operator has no prior intuitions in the domain → also research, not
  synthesis.
