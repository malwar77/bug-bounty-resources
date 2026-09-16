#!/usr/bin/env python3
import os
import re
import urllib.request
import urllib.error
import ssl
from concurrent.futures import ThreadPoolExecutor

repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url_regex = re.compile(r'\[([^\]]+)\]\((https?://[^\s\)]+|/[^\s\)]+|[a-zA-Z0-9_\-\./]+\.md[^\s\)]*)\)')
excluded_prefixes = (
    "https://twitter.com", "https://x.com", "https://www.linkedin.com",
    "https://linkedin.com", "https://medium.com", "https://www.youtube.com",
    "https://youtube.com", "https://amazon.com", "https://www.amazon.com",
    "https://amzn.to", "https://web.archive.org"
)

items = []
for root, dirs, files in os.walk(repo_dir):
    if any(p in root for p in ['.git', 'node_modules', '.github']):
        continue
    for file in sorted(files):
        if file.endswith('.md'):
            filepath = os.path.join(root, file)
            relpath = os.path.relpath(filepath, repo_dir)
            with open(filepath, 'r', encoding='utf-8') as f:
                for line_no, line in enumerate(f, 1):
                    for match in url_regex.finditer(line):
                        anchor, url = match.groups()
                        items.append((relpath, filepath, line_no, anchor.strip(), url.strip()))

def verify_target(relpath, filepath, line_no, anchor, url):
    if not url.startswith("http"):
        # Resolve relative to current md file
        clean_target = url.split('#')[0]
        if clean_target.startswith("/"):
            clean_target = clean_target.lstrip("/")
            resolved = os.path.join(repo_dir, clean_target)
        else:
            resolved = os.path.normpath(os.path.join(os.path.dirname(filepath), clean_target))
        exists = os.path.exists(resolved)
        return (relpath, line_no, url, 200 if exists else 404, "OK" if exists else "INTERNAL_FILE_MISSING")

    if any(url.startswith(p) for p in excluded_prefixes):
        return (relpath, line_no, url, 200, "EXCLUDED_WAF_BOT")

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    req = urllib.request.Request(url, headers=headers)
    try:
        req.get_method = lambda: 'HEAD'
        with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
            return (relpath, line_no, url, r.status, "OK")
    except Exception:
        try:
            req.get_method = lambda: 'GET'
            with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
                return (relpath, line_no, url, r.status, "OK")
        except urllib.error.HTTPError as e:
            return (relpath, line_no, url, e.code, f"HTTP {e.code}")
        except Exception as e:
            return (relpath, line_no, url, 0, str(e))

print(f"Checking {len(items)} links...")
with ThreadPoolExecutor(max_workers=15) as ex:
    results = list(ex.map(lambda x: verify_target(*x), items))

failed = [r for r in results if r[4] not in ("OK", "EXCLUDED_WAF_BOT") and r[3] not in (200, 204, 301, 302, 401, 403)]
print(f"Total links: {len(results)}, Issues: {len(failed)}")
for f in failed:
    print(f"::error file={f[0]},line={f[1]}::{f[2]} -> {f[4]}")
