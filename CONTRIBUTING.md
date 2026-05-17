# Contributing to cubething-qproj

Welcome! This is the human-facing entry point for working on this repo.
For agent-facing rules see [`AGENTS.md`](../../AGENTS.md); for deep-dive
reference see [`docs/bevy-best-practices/`](docs/bevy-best-practices/).

---

## Repo layout

Work is done inside a _metarepo,_ a workspace assembled from independent crates,
each living in its own bare-plus-worktree git layout.

```
cubething-qproj/
├── AGENTS.md              
├── Cargo.toml             # symlink -> infra/main/Cargo.toml
├── infra/                 # workspace infrastructure 
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

The AGENTS.md has a brief overview of branch naming conventions.

---

## Quick start

```sh
git clone https://github.com/cubething-qproj/infra --bare "$REPOS_ROOT/cubething-qproj/infra/.bare" 
echo "gitdir: ./.bare" > "$REPOS_ROOT/cubething-qproj/infra"
git -C "$REPOS_ROOT" worktree add main main
cd "$REPOS_ROOT/cubething-qproj" && ./infra/main/setup.sh
just sync
```

All primary actions are `just` recipes. Run `just` with no arguments for the full
list.

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
