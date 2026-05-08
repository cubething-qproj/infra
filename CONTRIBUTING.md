# Contributing to cubething-qproj

Welcome! This is the human-facing entry point for working on this repo.
For agent-facing rules see [`AGENTS.md`](../../AGENTS.md); for deep-dive
reference see [`docs/bevy-best-practices/`](docs/bevy-best-practices/).

---

## Repo layout

This is a **metarepo** — a workspace assembled from independent Rust
crates, each living in its own bare-plus-worktree git layout:

```
cubething-qproj/
├── AGENTS.md              # agent rules (always-on context)
├── Cargo.toml             # symlink → infra/main/Cargo.toml
├── justfile               # symlink → infra/main/metarepo.just
├── docs/
│   └── bevy-best-practices/   # reference material, on-demand reads
├── infra/                 # workspace infrastructure (own repo)
├── quell/active/          # the game crate
├── q_term/active/         # in-game terminal
├── q_screens/active/      # screen/scene lifecycle library
└── q_test_harness/active/ # Bevy testing harness
```

Each `<crate>/active` is a symlink into a worktree. The actual git layout
inside each crate directory is:

```
<crate>/
├── bare/         # bare clone of origin
├── main/         # worktree of origin/main
├── feat/<x>/     # feature worktrees as needed
└── active → main # symlink the workspace consumes
```

---

## Getting set up

1. Clone the metarepo (this includes only the orchestration scripts):
   ```sh
   git clone <metarepo-url>
   cd cubething-qproj
   ```
2. Run the setup script from `infra/` to materialize each crate's
   bare+worktree layout. Ask the operator if you need access to the
   private remotes.
3. Use a Nix shell or install the toolchain manually. The repo pins a
   specific nightly Rust (required by `bevy_lint`) — see
   `infra/main/flake.nix` or the toolchain pin in
   [`docs/bevy-best-practices/workspace-conventions.md`](docs/bevy-best-practices/workspace-conventions.md).
4. Verify your setup:
   ```sh
   just check
   just test
   ```

---

## Day-to-day commands

Everything is a `just` recipe. Run `just` with no arguments for the full
list; run `just ws` for workspace manipulation recipes. The most common
ones for editing crates:

| Recipe | What it does |
|---|---|
| `just play [args]` | Run the game (`quell`) |
| `just build [args]` | Build the workspace |
| `just check [args]` | clippy + bevy_lint across the workspace |
| `just clippy [args]` | clippy alone |
| `just bevy-lint [args]` | bevy_lint alone |
| `just test [args]` | nextest test runner |
| `just coverage [args]` | test coverage report |
| `just fix [args]` | clippy --fix |
| `just deny` | cargo-deny dependency audit |
| `just ci [args]` | run CI locally via `act` |

### Workspace manipulation (`just ws ...`)

Cross-repo and worktree operations live under `just ws`. These wrap the
`pj` scripts in `infra/main/pj/scripts/`. **Never** repoint an `active`
symlink by hand — use `just ws wt switch`.

| Recipe | What it does |
|---|---|
| `just ws wt add <repo> <branch>` | Create a worktree on `<branch>` and repoint `<repo>/active` to it. Branch is created from current `active` HEAD if it doesn't exist. Add `--no-switch` to skip the symlink update. |
| `just ws wt switch <repo> <wt>` | Repoint `<repo>/active` to an existing worktree. |
| `just ws wt rm <repo> <branch>` | Remove a worktree. Refuses `main` / current `active`. |
| `just ws wt ls [repo]` | List worktrees (all repos if no arg). |
| `just ws wt status` | Show the current `active` symlink target for every repo. |
| `just ws doctor` | Workspace health check across primary repos. |
| `just ws clean` | Clean stale worktrees / branches across primary repos. |
| `just ws install-git` | Install shared git hooks. |
| `just ws venv [args]` | Point basedpyright at a Python interpreter. |
| `just self-update` | Regenerate the metarepo justfile from the `infra` template. |

**Common worktree flow:**

```sh
just ws wt add q_term feat/cursor-blink   # creates and switches active
cd q_term/active                           # work on the new branch
# ... edit, commit ...
just ws wt switch q_term main              # switch back when done
just ws wt rm     q_term feat/cursor-blink # delete the worktree
```

Never invoke raw `cargo` for an operation that has a recipe — the
recipes wrap project-specific arguments and lint configuration. See
[`docs/bevy-best-practices/ci-and-tooling.md`](docs/bevy-best-practices/ci-and-tooling.md)
for the full catalog and rationale.

---

## Branching and commits

Inside any per-crate worktree, branch names follow:

```
main/                              # always-checked-out
feat/<change>                      # new features
feat/<initiative>/<sub-aspect>     # multi-PR initiatives, when designed
fix/<change>                       # bug fixes
docs/<change>                      # docs-only
ci/<change>                        # CI-only
tests/<change>                     # test-only
```

Create a new worktree from the bare clone for substantial work via
`just ws wt add <repo> <branch>`. Small fixes can go on a branch in the
existing `active` worktree, but ask first.

Base your work on `origin/main`. Fetch and rebase before opening a PR.

---

## Where the rules live

The codified Bevy + workspace conventions live under
[`docs/bevy-best-practices/`](docs/bevy-best-practices/). They're
organized so you can read just the file relevant to what you're working
on:

- **[bevy-conventions.md](docs/bevy-best-practices/bevy-conventions.md)**
  — plugin shape, module layout, observers, bundles, `Startup` rules.
- **[bevy-error-handling.md](docs/bevy-best-practices/bevy-error-handling.md)**
  — three-tier model: app handler, library `thiserror`, inline
  `tiny_bail`. When to use which.
- **[bevy-versioning.md](docs/bevy-best-practices/bevy-versioning.md)**
  — semi-conservative migration policy; how we handle Bevy minor bumps.
- **[workspace-conventions.md](docs/bevy-best-practices/workspace-conventions.md)**
  — `Cargo.toml` shape, lint config, feature flags, build profiles,
  toolchain pin.
- **[ci-and-tooling.md](docs/bevy-best-practices/ci-and-tooling.md)**
  — `just` recipes, doc generation, test harness defaults.

For `q_screens`-specific design and usage, build and read the crate's
own rustdoc:

```sh
cargo doc -p q_screens --open
```

This keeps the architecture description next to the code, so it can't
drift.

---

## Asking for help

- Architectural questions → ask the operator. The codified rules trace
  back to design notes that aren't in this repo.
- If a rule seems wrong: it might be. Open a discussion before changing
  it; the rules are explicit decisions, not defaults.

---

## Working with agents

If you use a coding agent (Claude, Cursor, Aider, pi, etc.) on this
repo, point it at [`AGENTS.md`](../../AGENTS.md) — the always-on rules — and
let it fetch the relevant `docs/bevy-best-practices/*.md` files
on-demand. The agent and human surfaces are deliberately split: AGENTS.md
is small and rule-shaped; this CONTRIBUTING.md is onboarding-shaped.
