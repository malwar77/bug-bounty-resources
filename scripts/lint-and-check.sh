#!/usr/bin/env bash
set -eo pipefail

echo "=== 1. Running Markdown Linting ==="
if command -v markdownlint-cli2 >/dev/null 2>&1; then
  markdownlint-cli2 "**/*.md" "#node_modules"
elif command -v npx >/dev/null 2>&1; then
  npx --yes markdownlint-cli2 "**/*.md" "#node_modules"
else
  echo "Notice: Neither markdownlint-cli2 nor npx found. Install via 'npm install -g markdownlint-cli2'."
fi

echo ""
echo "=== 2. Running Link Checker (lychee) ==="
if command -v lychee >/dev/null 2>&1; then
  lychee \
    --verbose \
    --no-progress \
    --exclude-mail \
    --max-concurrency 8 \
    --timeout 15 \
    --accept 200,204,401,403 \
    --exclude "^https://(twitter|x)\\.com" \
    --exclude "^https://(www\\.)?linkedin\\.com" \
    --exclude "^https://(www\\.)?youtube\\.com" \
    --exclude "^https://medium\\.com" \
    --exclude "^https://(www\\.)?amazon\\.com" \
    --exclude "^https://amzn\\.to" \
    --exclude "^https://web\\.archive\\.org" \
    "**/*.md"
elif command -v npx >/dev/null 2>&1; then
  echo "lychee is not in PATH. Running fallback link check with Python audit script..."
  python3 scripts/check_links.py
else
  echo "Notice: lychee CLI not installed. Run 'brew install lychee' or 'cargo install lychee'."
fi

echo "=== Checks complete ==="
