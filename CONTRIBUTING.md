# Contributing to cubething-qproj

Welcome! This is the human-facing entry point for working on this repo.
For agent-facing rules see [`AGENTS.md`](../../AGENTS.md); for deep-dive
reference see [`docs/bevy-best-practices/`](docs/bevy-best-practices/).

## Repo layout

Each crate is an ordinary Git checkout under `~/repos/cubething-qproj/`. Only
one branch is checked out per repository at a time.

Branch names follow:

```
main                               # default branch
feat/<change>                      # new features
feat/<initiative>/<sub-aspect>     # multi-PR initiatives, when designed
fix/<change>                       # bug fixes
chore/<change>                     # minor revisions
automation/<change>                # automated change repairs
doc/<change>                       # docs-only
tests/<change>                     # test-only
```

Use ordinary Git commands to create and switch branches.

Daily build and validation commands are available as `just` recipes. Run
`just` with no arguments for the full list.

## Guidelines

Best practice documents live here at docs/bevy-best-practices. Be sure to read
and understand them before opening a PR.
