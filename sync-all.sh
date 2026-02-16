#!/usr/bin/env bash
set -uo pipefail   # NOTE: removed -e (don't exit on error)

MAIN_BRANCH="main"

declare -A SUBTREES=(
  ["compliance-backend"]="https://github.com/shankarataxservices/compliance-backend.git"
)

echo "▶ Staging changes..."
git add -A

echo "▶ Committing if needed..."
git diff --cached --quiet || git commit -m "Auto sync $(date '+%Y-%m-%d %H:%M:%S')"

echo "▶ Pushing MAIN repo..."
if git push origin "$MAIN_BRANCH"; then
  echo "✔ Main repo pushed"
else
  echo "⚠ Main push failed — continuing with subtrees"
fi

echo "▶ Syncing subtrees..."

for DIR in "${!SUBTREES[@]}"; do
  REMOTE="${SUBTREES[$DIR]}"

  if [ ! -d "$DIR" ]; then
    echo "⚠ Missing folder: $DIR"
    continue
  fi

  echo "  → Splitting $DIR ..."

  SUB_COMMIT=$(git subtree split --prefix="$DIR")

  echo "  → Pushing to $REMOTE"

  if git push "$REMOTE" "$SUB_COMMIT:$MAIN_BRANCH"; then
    echo "  ✔ Subtree pushed"
  else
    echo "  ⚠ Normal push failed — forcing..."

    git push --force "$REMOTE" "$SUB_COMMIT:$MAIN_BRANCH" \
      && echo "  ✔ Forced push complete" \
      || echo "  ❌ Subtree push FAILED"
  fi
done

echo "✅ SYNC COMPLETE"
