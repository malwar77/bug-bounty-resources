#!/usr/bin/env bash
set -eo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== 1. Validating lychee.toml ==="
python3 scripts/validate_config.py

echo ""
echo "=== 2. Running Markdown Linting ==="
if command -v markdownlint-cli2 >/dev/null 2>&1; then
  markdownlint-cli2 "**/*.md" "#node_modules"
elif command -v npx >/dev/null 2>&1; then
  npx --yes markdownlint-cli2 "**/*.md" "#node_modules"
else
  echo "Notice: markdownlint-cli2/npx not found. Skipping linting."
fi

echo ""
echo "=== 3. Running Link Checker (reading lychee.toml + CLI flags) ==="
python3 scripts/check_links.py "$@"
GATE=$?
echo "=== Completed with exit status $GATE ==="
exit "$GATE"
