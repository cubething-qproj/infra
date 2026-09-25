# CI Architecture

This repo is the source of truth for the files in `scripts/src/qproj_scripts/assets/project-template/`. `qproj-scripts init` copies the whole template when creating a repo. When changes reach infra's `main`, `infra-sync-downstream.yml` copies shared files from that template to each registered downstream and opens a PR. It skips `Cargo.toml`, `README.md`, `src/`, `.gitignore`, `.zed/settings.json`, and `justfile`: those belong to each crate after initialization. The sync replaces `{{bevy_version}}` using `.bevy-version`. The template's thin `.github/workflows/ci.yml` calls `downstream-pipeline.yml` here via `workflow_call`. Passing sync PRs auto-merge; failures create an issue.

Build workflows use a composite action (`.github/actions/setup`) for Nix, Cargo caching, sccache, and apt dependencies. The dev shell is exported via `nicknovitski/nix-develop` so subsequent steps run without `nix develop --command` wrappers. Workflow files are prefixed by scope: `downstream-*` for reusable workflows and `infra-*` for workflows running on this repo.

```mermaid
graph TD
    subgraph infra["This repo (infra)"]
      subgraph templates["Project template"]
        TPL_CI[ci.yml]
        TPL_FLAKE[flake.nix]
      end

      SYNC["Sync on main push"]
      LINT["Lint on push or PR"]
      SETUP[actions/setup]
      DCI["Downstream pipeline"]
    end

    subgraph downstream["Downstream repos"]
      DS_CI[ci.yml]
      DS_FLAKE[flake.nix]
    end

    SYNC -- syncs --> templates
    TPL_CI -. template .-> DS_CI
    TPL_FLAKE -. template .-> DS_FLAKE
    DS_CI -- workflow_call --> DCI
    DCI --> SETUP
```
