#!/usr/bin/env python3
"""Config-driven link checker with CLI flag and environment variable overrides.
Reads lychee.toml by default, applies quality-gate rules, and formats PR annotations.
"""
import argparse
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

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url_regex = re.compile(r'\[([^\]]+)\]\((https?://[^\s\)]+|/[^\s\)]+|[a-zA-Z0-9_\-\./]+\.md[^\s\)]*)\)')
headers_ua = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

VALID_CATEGORIES = {
    "BROKEN_NOT_FOUND", "BROKEN_INTERNAL_FILE", "TIMEOUT_OR_DNS_FAILURE",
    "HTTP_5XX", "HTTP_4XX", "REDIRECTED", "BOT_PROTECTED_OR_AUTH",
    "PASSED", "PASSED_EXCLUDED"
}


def parse_args():
    parser = argparse.ArgumentParser(description="Audits links in markdown files against configured rules.")
    parser.add_argument("--config", default="lychee.toml", help="Path to lychee.toml configuration file")
    parser.add_argument("--timeout", type=int, default=None, help="HTTP request timeout in seconds")
    parser.add_argument("--concurrency", type=int, default=None, help="Maximum concurrent requests")
    parser.add_argument("--cache-dir", default=None, help="Path to cache directory")
    parser.add_argument("--quality-gate", default=None, help="Comma-separated categories that cause build failure")
    parser.add_argument("--warning-categories", default=None, help="Comma-separated categories that produce warnings")
    parser.add_argument("--target-dir", default=None, help="Directory or file path to audit (defaults to repo root)")
    parser.add_argument("--output-json", default="audit/link-report.json", help="Path to output JSON report")
    return parser.parse_args()


def load_config(config_path):
    if os.path.exists(config_path):
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    return {}


def main():
    args = parse_args()
    cfg = load_config(args.config)

    timeout = args.timeout or int(os.environ.get("LINKCHECK_TIMEOUT", str(cfg.get("timeout", 15))))
    concurrency = args.concurrency or int(os.environ.get("LINKCHECK_CONCURRENCY", str(cfg.get("max_concurrency", 8))))
    accept = set(int(x) for x in cfg.get("accept", [200, 204, 401, 403]))
    excluded = [re.compile(p.replace("\\\\", "\\")) for p in cfg.get("exclude", [])]

    raw_qg = args.quality_gate or os.environ.get("QUALITY_GATE_CATEGORIES", "BROKEN_NOT_FOUND,BROKEN_INTERNAL_FILE,TIMEOUT_OR_DNS_FAILURE,HTTP_5XX")
    quality_gate = set(x.strip() for x in raw_qg.split(",") if x.strip())

    raw_warn = args.warning_categories or os.environ.get("WARNING_CATEGORIES", "REDIRECTED,BOT_PROTECTED_OR_AUTH")
    warning_categories = set(x.strip() for x in raw_warn.split(",") if x.strip())

    base_dir = os.path.abspath(args.target_dir or os.path.join(os.path.dirname(__file__), ".."))

    def is_excluded(url):
        return any(p.search(url) for p in excluded)

    def classify(code, final_url, orig_url, msg):
        if code in accept:
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
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                return r.status, r.geturl(), "OK"
        except Exception:
            try:
                req.get_method = lambda: 'GET'
                with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                    return r.status, r.geturl(), "OK"
            except urllib.error.HTTPError as e:
                return e.code, url, f"HTTPError {e.code}: {e.reason}"
            except Exception as e:
                return 0, url, str(e)

    items = []
    if os.path.isfile(base_dir):
        files_to_scan = [base_dir]
        walk_root = os.path.dirname(base_dir)
    else:
        files_to_scan = []
        walk_root = base_dir
        for root, dirs, files in os.walk(base_dir):
            if any(p in root for p in ['.git', 'node_modules', '.github']):
                continue
            for file in sorted(files):
                if file.endswith('.md'):
                    files_to_scan.append(os.path.join(root, file))

    for filepath in files_to_scan:
        relpath = os.path.relpath(filepath, walk_root)
        with open(filepath, 'r', encoding='utf-8') as f:
            for line_no, line in enumerate(f, 1):
                for m in url_regex.finditer(line):
                    anchor, url = m.groups()
                    items.append((relpath, filepath, line_no, anchor.strip(), url.strip()))

    print(f"Checking {len(items)} links (timeout={timeout}s, concurrency={concurrency})...")

    def run_check(item):
        relpath, filepath, line_no, anchor, url = item
        if not url.startswith("http"):
            target = url.split('#')[0]
            if target.startswith('/'):
                resolved = os.path.join(walk_root, target.lstrip('/'))
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

    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        results = list(ex.map(run_check, items))

    warnings, failures, passed = [], [], []
    for relpath, line_no, url, code, cat, dest in results:
        entry = {"file": relpath, "line": line_no, "url": url, "status": code, "category": cat, "destination": dest}
        if cat in quality_gate:
            failures.append(entry)
            print(f"::error file={relpath},line={line_no}::{cat} (HTTP {code}) {url} -> {dest}")
        elif cat in warning_categories or cat in ("REDIRECTED", "BOT_PROTECTED_OR_AUTH"):
            warnings.append(entry)
            print(f"::warning file={relpath},line={line_no}::{cat} (HTTP {code}) {url} -> {dest}")
        else:
            passed.append(entry)

    # Output report
    out_json = os.path.join(walk_root, args.output_json) if not os.path.isabs(args.output_json) else args.output_json
    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({
            "summary": {
                "total": len(results),
                "passed": len(passed),
                "warnings": len(warnings),
                "failures": len(failures)
            },
            "quality_gate": sorted(quality_gate),
            "warning_categories": sorted(warning_categories),
            "failures": failures,
            "warnings": warnings
        }, f, indent=2)

    print(f"Total: {len(results)} | Passed: {len(passed)} | Warnings: {len(warnings)} | Gate failures: {len(failures)}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
