#!/usr/bin/env bash
set -euo pipefail

ORG="cubething-qproj"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

REPOS=(q_screens q_term q_test_harness quell)
DOWNSTREAM=(infra)

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
	cp "$SCRIPT_DIR/just/metarepo.just" "$ROOT/justfile"
	echo "✓ justfile copied from template"
else
	echo "✓ justfile exists (run 'just self-update' to refresh)"
fi

# Seed root AGENTS.md from infra template (chezmoi create_-style:
# copy once on first init; never clobber a real file the operator has
# customized).
agents_src="$SCRIPT_DIR/AGENTS.metarepo.md"
agents_dst="$ROOT/AGENTS.md"
if [ ! -e "$agents_dst" ]; then
	if [ ! -f "$agents_src" ]; then
		echo "✗ AGENTS.metarepo.md missing at $agents_src" >&2
		exit 1
	fi
	cp "$agents_src" "$agents_dst"
	echo "✓ AGENTS.md seeded from infra/main/AGENTS.metarepo.md"
else
	echo "✓ AGENTS.md exists (operator-owned; diff against"
	echo "   infra/main/AGENTS.metarepo.md to pick up template updates)"
fi

# Detect GPU vendor for the right nix devshell variant. Mirrors the
# logic in infra/main/scripts/play.py:_autodetect_nixgl. NVIDIA hosts
# need the #nvidia devshell (carries nixVulkanNvidia + the unfree
# driver); Intel/AMD use the default shell (carries nixVulkanIntel).
detect_gpu_suffix() {
	if [ -e /proc/driver/nvidia/version ]; then
		echo "#nvidia"
		return
	fi
	for f in /sys/class/drm/card*/device/vendor; do
		[ -e "$f" ] || continue
		case "$(cat "$f" 2>/dev/null)" in
			0x10de) echo "#nvidia"; return ;;
		esac
	done
	echo ""
}
flake_suffix="$(detect_gpu_suffix)"
if [ -n "$flake_suffix" ]; then
	echo "✓ detected NVIDIA GPU; .envrc will use flake variant '$flake_suffix'"
else
	echo "✓ no NVIDIA GPU detected; .envrc will use default flake variant"
fi

# Write root .envrc (exports env needed by ws recipes + flake).
# Exports MUST come before `use flake` -- the flake's eval depends on
# NIXPKGS_ALLOW_UNFREE (NVIDIA driver is unfree) and nixGL needs
# --impure for `builtins.currentTime`. Direnv applies exports in source
# order, so reordering breaks evaluation.
envrc="$ROOT/.envrc"
cat >"$envrc" <<EOF
export PROJECT_ROOT="\$(pwd)"
export PRIMARY_OWNER="$ORG"
export PRIMARY_REPOS="${REPOS[*]}"
export DOWNSTREAM_REPOS="${DOWNSTREAM[*]}"
export GH_TOKEN=\$(gh auth token 2>/dev/null || echo "")
export NIXPKGS_ALLOW_UNFREE=1
export LOCAL=1

# GPU-variant autodetected by setup.sh. Override by editing the suffix
# (e.g. drop '#nvidia' for the default shell, or change to a different
# variant). Re-running setup.sh will re-detect and overwrite.
use flake --impure ./infra/main${flake_suffix}
EOF
echo "✓ .envrc written"

echo ""
echo "All repos ready at $ROOT/"
echo "Run 'direnv allow' in $ROOT/, then 'just --list' to verify."
