#!/usr/bin/env bash
set -euo pipefail

ORG="cubething-qproj"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

REPOS=(q_screens q_term q_test_harness quell)

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

# Create root-level symlinks
echo ""
echo "Creating root symlinks..."
for f in Cargo.toml Cargo.lock justfile; do
	link="$ROOT/$f"
	target="infra/main/$f"
	if [ -L "$link" ]; then
		echo "✓ $f symlink exists"
	else
		ln -s "$target" "$link"
		echo "✓ $f symlink created"
	fi
done

# Create root .envrc if missing
if [ ! -f "$ROOT/.envrc" ]; then
	echo "use flake ./infra/main" >"$ROOT/.envrc"
	echo "✓ .envrc created"
else
	echo "✓ .envrc exists"
fi

echo ""
echo "All repos ready at $ROOT/"
echo "Run 'just build' from $SCRIPT_DIR/ to verify."
