#!/usr/bin/env bash
# ------------------------------------------
# SPDX-License-Identifier: MIT OR Apache-2.0
# -------------------------------- 𝒒𝒑𝒓𝒐𝒋 --
#
# wt.sh — worktree management for the qproj workspace
#
# Manages git worktrees and `active` symlinks across the multi-repo workspace.
# Each crate repo has an `active` symlink that points to whichever worktree
# (branch) is currently in use by the Cargo workspace. Switching the active
# branch is a symlink repoint — no Cargo.toml edits needed.
#
# Usage:
#   wt.sh add <repo> <branch>   — create worktree and switch active
#   wt.sh rm  <repo> <branch>   — remove worktree (refuses main)
#   wt.sh ls  [repo]            — list worktrees
#   wt.sh status                — show active symlinks

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

CRATE_REPOS=(quell q_screens q_term q_test_harness)

# ── helpers ──────────────────────────────────────────────────────────

usage() {
	cat <<-EOF
		Usage: wt.sh <command> [args]

		Commands:
		  add <repo> <branch>   Create worktree and switch active symlink
		  rm  <repo> <branch>   Remove worktree (refuses to remove main)
		  ls  [repo]            List worktrees (all repos if none specified)
		  status                Show active symlink targets
	EOF
	exit 1
}

validate_repo() {
	local repo="$1"
	for r in "${CRATE_REPOS[@]}"; do
		if [[ "$r" == "$repo" ]]; then
			return 0
		fi
	done
	echo "error: unknown repo '$repo'"
	echo "valid repos: ${CRATE_REPOS[*]}"
	exit 1
}

# ── commands ─────────────────────────────────────────────────────────

cmd_add() {
	if [[ $# -lt 2 ]]; then
		echo "Usage: wt.sh add <repo> <branch>"
		exit 1
	fi

	local repo="$1"
	local branch="$2"
	validate_repo "$repo"

	local repo_dir="$ROOT/$repo"

	# Create branch if it doesn't exist
	if ! git -C "$repo_dir" rev-parse --verify "$branch" &>/dev/null; then
		# Get the current active worktree's HEAD as the base
		local active_target
		active_target="$(readlink "$repo_dir/active")"
		echo "Creating branch '$branch' from '$active_target'..."
		git -C "$repo_dir/$active_target" branch "$branch"
	fi

	# Create worktree if it doesn't exist
	if [[ ! -d "$repo_dir/$branch" ]]; then
		echo "Creating worktree '$repo/$branch'..."
		git -C "$repo_dir" worktree add "$branch" "$branch"
	fi

	# Safety check: Cargo.toml must exist in the worktree
	if [[ ! -f "$repo_dir/$branch/Cargo.toml" ]]; then
		echo "error: $repo/$branch/Cargo.toml not found"
		echo "The worktree was created but may be on an incompatible branch."
		exit 1
	fi

	# Repoint the active symlink
	ln -sfn "$branch" "$repo_dir/active"
	echo "✓ $repo/active → $branch"
}

cmd_rm() {
	if [[ $# -lt 2 ]]; then
		echo "Usage: wt.sh rm <repo> <branch>"
		exit 1
	fi

	local repo="$1"
	local branch="$2"
	validate_repo "$repo"

	if [[ "$branch" == "main" ]]; then
		echo "error: refusing to remove the 'main' worktree"
		exit 1
	fi

	local repo_dir="$ROOT/$repo"

	# If active points to this branch, switch back to main first
	local active_target
	active_target="$(readlink "$repo_dir/active")"
	if [[ "$active_target" == "$branch" ]]; then
		echo "Switching $repo/active back to main..."
		ln -sfn main "$repo_dir/active"
		echo "✓ $repo/active → main"
	fi

	# Remove the worktree
	if [[ -d "$repo_dir/$branch" ]]; then
		git -C "$repo_dir" worktree remove "$branch"
		echo "✓ $repo/$branch worktree removed"
	else
		echo "$repo/$branch does not exist"
	fi
}

cmd_ls() {
	local repos=("${CRATE_REPOS[@]}")
	if [[ $# -ge 1 ]]; then
		validate_repo "$1"
		repos=("$1")
	fi

	for repo in "${repos[@]}"; do
		local repo_dir="$ROOT/$repo"
		local active_target
		active_target="$(readlink "$repo_dir/active" 2>/dev/null || echo "?")"

		echo "── $repo (active → $active_target) ──"
		git -C "$repo_dir" worktree list
		echo ""
	done
}

cmd_status() {
	for repo in "${CRATE_REPOS[@]}"; do
		local repo_dir="$ROOT/$repo"
		local active_target
		active_target="$(readlink "$repo_dir/active" 2>/dev/null || echo "NOT SET")"
		echo "$repo/active → $active_target"
	done
}

# ── main ─────────────────────────────────────────────────────────────

case "${1:-}" in
add)
	shift
	cmd_add "$@"
	;;
rm)
	shift
	cmd_rm "$@"
	;;
ls)
	shift
	cmd_ls "$@"
	;;
status)
	shift
	cmd_status "$@"
	;;
*) usage ;;
esac
