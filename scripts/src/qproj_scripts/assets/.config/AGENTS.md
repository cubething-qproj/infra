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

This is a "metarepo." It is not a git repository, but a project-level working
tree.

Git repositories in this directory are typically checked out as a bare +
worktree layout, but some less active repos are plain git clones.

Hidden directories are not part of the project. They include personal
configuration.

## Governance

When you enter any new directory, the first thing you MUST do is read its
governance files. Governance files include AGENTS.md, AGENTS.local.md,
README.md, CLAUDE.md, CURSOR.md, .github/copilot-instructions, CONTRIBUTING.md,
HACKING.md, etc. Failure to read these files is a critical error.

## Worktrees

Worktrees should have one of the following prefixes:

- feat/ # new features
- fix/ # bug fixes
- release/ # release branches - rare!
- doc/ # documentation
- tests/ # testing - new tests, test edits, etc.

The exception is the default branch, `main`. you should not modify this branch,
it is for reference only. Fetch and pull each time you reference it, so it
always stays up to date.

All worktrees should have relative git dirs. If you need to update git, then do so.

Use the justfile for worktree management. Do NOT retarget 'active' unless
specifically asked to do so.

## When to read what (reference material)

Fetch these on-demand based on what you're touching:

| Touching...                                        | Read...                    |
| -------------------------------------------------- | -------------------------- |
| Any `Cargo.toml`                                   | `workspace-conventions.md` |
| Plugin / system / module structure                 | `bevy-conventions.md`      |
| Anything that returns `Result` or uses `tiny_bail` | `bevy-error-handling.md`   |
| Bumping a Bevy-related dep                         | `bevy-versioning.md`       |
