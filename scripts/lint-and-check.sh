#!/usr/bin/env bash
set -eo pipefail
# Local checks with the same configuration as CI (reads lychee.toml).
# Override with env vars: LINKCHECK_TIMEOUT, LINKCHECK_CONCURRENCY, QUALITY_GATE_CATEGORIES.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== 1. Markdown Linting ==="
if command -v markdownlint-cli2 >/dev/null 2>&1; then
  markdownlint-cli2 "**/*.md" "#node_modules"
elif command -v npx >/dev/null 2>&1; then
  npx --yes markdownlint-cli2 "**/*.md" "#node_modules"
else
  echo "Notice: markdownlint-cli2/npx not found. Install Node.js 18+ first."
fi

echo ""
echo "=== 2. Link Checking (lychee.toml + scripts/check_links.py) ==="
if command -v lychee >/dev/null 2>&1; then
  # lychee picks up lychee.toml automatically; env vars override for parity with CI
  lychee \
    --no-progress \
    --cache \
    --max-cache-age 1d \
    --timeout "${LINKCHECK_TIMEOUT:-15}" \
    --max-concurrency "${LINKCHECK_CONCURRENCY:-8}" \
    --output lychee-report.md \
    --format markdown \
    "**/*.md" || true
fi

python3 scripts/check_links.py
GATE=$?
echo "=== Checks complete (quality gate exit: $GATE) ==="
exit "$GATE"
