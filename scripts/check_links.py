#!/usr/bin/env python3
"""Local link checker aligned with CI. Reads lychee.toml for config so CI and local never drift.

Quality gate: exits 1 only for categories listed in QUALITY_GATE_CATEGORIES
(comma-separated). Redirects and bot-protected links are reported as warnings.
Annotations use ::error file=...,line=...:: with category, status, and destination.
"""
import os
import re
import sys
import json
import urllib.request
import urllib.error
import ssl
from concurrent.futures import ThreadPoolExecutor

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

REPO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# ---------- Load shared config (lychee.toml) ----------
CONFIG_PATH = os.path.join(REPO_DIR, "lychee.toml")
cfg = {}
if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, "rb") as f:
        cfg = tomllib.load(f)

# Env overrides (mirror CI inputs)
TIMEOUT = int(os.environ.get("LINKCHECK_TIMEOUT", str(cfg.get("timeout", 15))))
CONCURRENCY = int(os.environ.get("LINKCHECK_CONCURRENCY", str(cfg.get("max_concurrency", 8))))
ACCEPT = set(int(x) for x in cfg.get("accept", [200, 204, 401, 403]))
EXCLUDED = [re.compile(p.replace("\\\\", "\\")) for p in cfg.get("exclude", [])]
QUALITY_GATE_CATEGORIES = set(
    x.strip() for x in os.environ.get(
        "QUALITY_GATE_CATEGORIES",
        "BROKEN_NOT_FOUND,BROKEN_INTERNAL_FILE,TIMEOUT_OR_DNS_FAILURE,HTTP_5XX"
    ).split(",") if x.strip()
)

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url_regex = re.compile(r'\[([^\]]+)\]\((https?://[^\s\)]+|/[^\s\)]+|[a-zA-Z0-9_\-\./]+\.md[^\s\)]*)\)')
headers_ua = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}


def is_excluded(url):
    return any(p.search(url) for p in EXCLUDED)


def classify(code, final_url, orig_url, msg):
    if code in ACCEPT:
        if final_url and final_url.rstrip('/') != orig_url.rstrip('/'):
            return "REDIRECTED", final_url
        return "PASSED", final_url or orig_url
    if code in (401, 403):
        return "BOT_PROTECTED_OR_AUTH", orig_url
    if code in (404, 410):
        return "BROKEN_NOT_FOUND", orig_url
    if 500 <= code < 600:
        return "HTTP_5XX", orig_url
    if code == 0:
        return "TIMEOUT_OR_DNS_FAILURE", orig_url
    return f"HTTP_{code}", orig_url


def probe(url):
    req = urllib.request.Request(url, headers=headers_ua)
    try:
        req.get_method = lambda: 'HEAD'
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as r:
            return r.status, r.geturl(), "OK"
    except Exception:
        try:
            req.get_method = lambda: 'GET'
            with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as r:
                return r.status, r.geturl(), "OK"
        except urllib.error.HTTPError as e:
            return e.code, url, f"HTTPError {e.code}: {e.reason}"
        except Exception as e:
            return 0, url, str(e)


items = []
for root, dirs, files in os.walk(REPO_DIR):
    if any(p in root for p in ['.git', 'node_modules', '.github']):
        continue
    for file in sorted(files):
        if file.endswith('.md'):
            filepath = os.path.join(root, file)
            relpath = os.path.relpath(filepath, REPO_DIR)
            with open(filepath, 'r', encoding='utf-8') as f:
                for line_no, line in enumerate(f, 1):
                    for m in url_regex.finditer(line):
                        anchor, url = m.groups()
                        items.append((relpath, filepath, line_no, anchor.strip(), url.strip()))

print(f"Checking {len(items)} links (timeout={TIMEOUT}s, concurrency={CONCURRENCY})...")


def run(item):
    relpath, filepath, line_no, anchor, url = item
    if not url.startswith("http"):
        target = url.split('#')[0]
        if target.startswith('/'):
            resolved = os.path.join(REPO_DIR, target.lstrip('/'))
        else:
            resolved = os.path.normpath(os.path.join(os.path.dirname(filepath), target))
        exists = os.path.exists(resolved)
        cat, dest = ("PASSED", url) if exists else ("BROKEN_INTERNAL_FILE", url)
        return (relpath, line_no, url, 200 if exists else 404, cat, dest)
    if is_excluded(url):
        return (relpath, line_no, url, 200, "PASSED_EXCLUDED", url)
    code, final, msg = probe(url)
    cat, dest = classify(code, final, url, msg)
    return (relpath, line_no, url, code, cat, dest)


with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
    results = list(ex.map(run, items))

warnings, failures = [], []
for relpath, line_no, url, code, cat, dest in results:
    entry = {"file": relpath, "line": line_no, "url": url, "status": code, "category": cat, "destination": dest}
    if cat in ("PASSED", "PASSED_EXCLUDED", "REDIRECTED", "BOT_PROTECTED_OR_AUTH"):
        if cat in ("REDIRECTED", "BOT_PROTECTED_OR_AUTH"):
            warnings.append(entry)
            print(f"::warning file={relpath},line={line_no}::{cat} (HTTP {code}) {url} -> {dest}")
    elif cat in QUALITY_GATE_CATEGORIES:
        failures.append(entry)
        print(f"::error file={relpath},line={line_no}::{cat} (HTTP {code}) {url} -> {dest}")
    else:
        warnings.append(entry)
        print(f"::warning file={relpath},line={line_no}::{cat} (HTTP {code}) {url} -> {dest}")

# JSON report for CI artifacts
os.makedirs(os.path.join(REPO_DIR, "audit"), exist_ok=True)
report = {
    "summary": {"total": len(results), "passed": len(results) - len(warnings) - len(failures),
                "warnings": len(warnings), "failures": len(failures)},
    "warnings": warnings, "failures": failures
}
with open(os.path.join(REPO_DIR, "audit", "link-report.json"), "w") as f:
    json.dump(report, f, indent=2)

print(f"Total: {len(results)} | Warnings: {len(warnings)} | Gate failures: {len(failures)}")
print(f"Failing categories: {sorted(QUALITY_GATE_CATEGORIES)}")
sys.exit(1 if failures else 0)
