#!/usr/bin/env bash
set -euo pipefail

MAIN_BRANCH="main"

# ========= CONFIG: MAP SUBDIR → REMOTE REPO =========
# Add as many as you want

declare -A SUBTREES=(
  ["compliance-backend"]="https://github.com/shankarataxservices/compliance-backend.git"
  # ["another-folder"]="https://github.com/user/another-repo.git"
)

# ========= OPTIONAL EXCLUSIONS =========
EXCLUDES=(
  ".git"
  "node_modules"
)

echo "▶ Staging changes..."

# Add everything except excluded folders
git add -A

for ex in "${EXCLUDES[@]}"; do
  git reset -q HEAD -- "$ex" 2>/dev/null || true
done

echo "▶ Committing if needed..."

if ! git diff --cached --quiet; then
  git commit -m "Auto sync $(date '+%Y-%m-%d %H:%M:%S')"
else
  echo "✔ Nothing to commit"
fi

echo "▶ Pulling remote to preserve history..."
git pull origin "$MAIN_BRANCH" --no-rebase --no-edit || true

echo "▶ Pushing MAIN repo..."
git push origin "$MAIN_BRANCH"

echo "▶ Syncing subtrees..."

for DIR in "${!SUBTREES[@]}"; do
  REMOTE="${SUBTREES[$DIR]}"

  if [ ! -d "$DIR" ]; then
    echo "⚠ Skipping missing folder: $DIR"
    continue
  fi

  echo "  → Processing $DIR"

  SUB_COMMIT=$(git subtree split --prefix="$DIR")

  git push "$REMOTE" "$SUB_COMMIT:$MAIN_BRANCH" || {
    echo "  ⚠ Non-fast-forward — retrying with pull/merge..."

    git fetch "$REMOTE" "$MAIN_BRANCH" || true

    git push "$REMOTE" "$SUB_COMMIT:$MAIN_BRANCH"
  }
done

echo "✅ ALL REPOSITORIES SYNCED SAFELY"
