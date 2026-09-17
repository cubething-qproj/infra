# AGENTS.md — cubething-qproj metarepo

This is the always-on context for agents working in this repo. Rules here
apply to **every** code-touching action. Reference material lives under
`infra/main/docs/bevy-best-practices/` and is fetched
on-demand when a relevant tool call happens.

Use this script to list all the docs and their URLs.

```sh
curl -fsSL https://api.github.com/repos/cubething-qproj/infra/contents/docs/bevy-best-practices?ref=main \
     | jq -r '.[] | "\(.type)\t\(.name)\t\(.download_url // "-")"'
```

## Directory structure

Each repository is an ordinary Git checkout. Only one working tree exists per
repository; use ordinary Git commands to switch branches in place.

Generated local configuration may be excluded through `.git/info/exclude`.

## Governance

When you enter any new directory, the first thing you MUST do is read its
governance files. Governance files include AGENTS.md, AGENTS.local.md,
README.md, CLAUDE.md, CURSOR.md, .github/copilot-instructions, CONTRIBUTING.md,
HACKING.md, etc. Failure to read these files is a critical error.

## Branches

Branches should have one of the following prefixes:

- feat/ # new features
- fix/ # bug fixes
- chore/ # minor revisions
- automation/ # automated change repairs
- release/ # release branches - rare!
- doc/ # documentation
- tests/ # testing - new tests, test edits, etc.

The exception is the default branch, `main`; do not modify it directly. Fetch
before referencing it so it stays up to date.

## When to read what (reference material)

Fetch these on-demand based on what you're touching:

| Touching...                                        | Read...                    |
| -------------------------------------------------- | -------------------------- |
| Any `Cargo.toml`                                   | `workspace-conventions.md` |
| Plugin / system / module structure                 | `bevy-conventions.md`      |
| Anything that returns `Result` or uses `tiny_bail` | `bevy-error-handling.md`   |
| Bumping a Bevy-related dep                         | `bevy-versioning.md`       |
