# Contributing to cubething-qproj

Welcome! This is the human-facing entry point for working on this repo.
For agent-facing rules see [`AGENTS.md`](../../AGENTS.md); for deep-dive
reference see [`docs/bevy-best-practices/`](docs/bevy-best-practices/).

## Repo layout

Work is done inside a _metarepo,_ a workspace assembled from independent crates,
each living in its own bare-plus-worktree git layout.

Each `<crate>/active` is a symlink into a worktree. The AGENTS.md in qproj_scripts/assets has a brief overview of branch naming conventions.


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

Create a new worktree from the bare clone for substantial work via `just add
<name>`, then target it for editing with `just target <name>`.

Your daily commands are `just` recipes. Run `just` with no arguments for the
full list.

## Guidelines

Best practice documents live here at docs/bevy-best-practices. Be sure to read
and understand them before opening a PR.
