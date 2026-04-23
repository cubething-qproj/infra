#!/usr/bin/env bash
set -euo pipefail

ORG="cubething-qproj"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

REPOS=(q_screens q_term q_test_harness quell)

# Initialize submodules (pj).
echo "Initializing submodules..."
git -C "$SCRIPT_DIR" submodule update --init --recursive

for repo in "${REPOS[@]}"; do
	dir="$ROOT/$repo"
	if [ -d "$dir/.bare" ]; then
		echo "✓ $repo already set up"
		continue
	fi

	echo "Cloning $ORG/$repo..."
	mkdir -p "$dir"
	git clone --bare "git@github.com:$ORG/$repo.git" "$dir/.bare"
	echo "gitdir: .bare" >"$dir/.git"

	default_branch=$(git -C "$dir/.bare" symbolic-ref --short HEAD \
		2>/dev/null || echo main)
	git -C "$dir" worktree add main "$default_branch"
	echo "✓ $repo ready"
done

# Create active symlinks (default to main)
for repo in "${REPOS[@]}"; do
	link="$ROOT/$repo/active"
	if [ -L "$link" ] && [ -e "$link" ]; then
		echo "✓ $repo/active symlink exists"
	else
		[ -L "$link" ] && rm "$link" # remove dangling symlink
		ln -s main "$link"
		echo "✓ $repo/active symlink created"
	fi
done

# Create root-level symlinks (idempotent — `ln -sfn` replaces existing symlinks;
# a pre-existing real file/dir at the target will still cause ln to fail, which
# is the intended safety).
echo ""
echo "Creating root symlinks..."
for f in Cargo.toml Cargo.lock justfile .cargo .config .zed; do
	link="$ROOT/$f"
	target="infra/main/$f"
	if [ -e "$link" ] && [ ! -L "$link" ]; then
		echo "⚠  $f exists as a real file/dir at metarepo root; skipping"
		echo "   (remove it manually if you want the symlink recreated)"
		continue
	fi
	ln -sfn "$target" "$link"
	echo "✓ $f → $target"
done

# Copy root justfile from template
if [ ! -f "$ROOT/justfile" ] || [ -L "$ROOT/justfile" ]; then
	[ -L "$ROOT/justfile" ] && rm "$ROOT/justfile"
	cp "$SCRIPT_DIR/metarepo.just" "$ROOT/justfile"
	echo "✓ justfile copied from template"
else
	echo "✓ justfile exists (run 'just self-update' to refresh)"
fi

# Write root .envrc (exports env needed by ws recipes + flake).
envrc="$ROOT/.envrc"
cat >"$envrc" <<EOF
use flake ./infra/main

export PROJECT_ROOT="\$(pwd)"
export PRIMARY_OWNER="$ORG"
export PRIMARY_REPOS="${REPOS[*]}"
export GH_TOKEN=\$(gh auth token 2>/dev/null || echo "")
EOF
echo "✓ .envrc written"

echo ""
echo "All repos ready at $ROOT/"
echo "Run 'direnv allow' in $ROOT/, then 'just --list' to verify."
