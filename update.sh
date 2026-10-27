#!/bin/bash
REPO="${UPSTREAM_REPO:-}"
BRANCH="${UPSTREAM_BRANCH:-main}"

set -e
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"

if [ -z "$REPO" ]; then
    echo "UPSTREAM_REPO not set"
    exit 1
fi

[ -d .git ] || git init -q
if git remote get-url origin >/dev/null 2>&1; then
    git remote set-url origin "$REPO"
else
    git remote add origin "$REPO"
fi

OLD="$(git rev-parse --verify -q HEAD 2>/dev/null || true)"
git fetch origin "$BRANCH"
git reset --hard FETCH_HEAD

if [ -f requirements.txt ]; then
    if [ -z "$OLD" ] || ! git diff --quiet "$OLD" HEAD -- requirements.txt; then
        if "$PY" -m pip install -q -r requirements.txt; then
            echo "✅ requirements installed"
        else
            echo "⚠️ pip install failed"
        fi
    fi
fi

echo "✅ Updated to $(git rev-parse --short HEAD). Restart the bot now."
