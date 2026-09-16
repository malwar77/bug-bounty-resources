# Bug Bounty Hunting Resources # Resources-for-Beginner-Bug-Bounty-Hunters Guide

> Originally curated by [NahamSec (Ben Sadeghipour)](https://github.com/nahamsec/Resources-for-Beginner-Bug-Bounty-Hunters) and open-source contributors.




## Intro
### Current Version: 2023.01
Welcome to our web hacking and bug bounty hunting resource repository! A curated collection of web hacking tools, tips, and resources is available here. We hope that this repository will be a valuable resource for you as you work to secure the internet and make it a safer place for everyone, whether you're a seasoned bug bounty hunter or just getting started.

We understand that there are more resources other than the ones we have listed and we hope to cover more resources in the near future!<br>

If you are interested in learning about top bug bounty hunters in the community check out my [Live Recon VODs](https://www.youtube.com/playlist?list=PLKAaMVNxvLmAkqBkzFaOxqs3L66z2n8LA).


## NahamSec's Personal Resource:
I have also put together my own resource:

- [NahamSec's Bug Bounty Course with 100+ Labs](https://app.hackinghub.io/hubs/nahamsec-bug-bounty-course)
- [Nahamsec on YouTube](https://www.youtube.com/NahamSec) 
- [Nahamsec on Twitch](https://www.twitch.tv/nahamsec)

---
## Table of Contents

- [Basics](./assets/basics.md)
- [Blog posts & Talks](./assets/blogposts.md)
- [Books](./assets/books.md)
- [Setup](./assets/setup.md)
- [Tools](./assets/tools.md)
- [Labs & Testing Environments](./assets/labs.md)
- [Talks](./assets/talks.md)
- [Vulnerability Types](./assets/vulns.md)
- [Mobile Hacking](./assets/mobile.md)
- [Coding & Scripting](./assets/coding.md)
- [Media Resources](./assets/media.md)
- [Mindset & Mental Health](./assets/health.md)

---
If you have more questions or suggestions, check out [NahamSec's Discord](https://discord.gg/9jZxjQ5)!<br>

---

## Local Development & Link Auditing

To prevent broken links and formatting regressions before submitting changes:

```bash
# Make the check script executable (if needed) and run
chmod +x scripts/lint-and-check.sh
./scripts/lint-and-check.sh
```

Or run the Python fallback directly:
```bash
python3 scripts/check_links.py
```

### Pre-requisites
- **Node.js 18+** (for `markdownlint-cli2`)
- **Python 3.8+**
- Optional: [lychee CLI](https://github.com/lycheeverse/lychee) (`brew install lychee` or `cargo install lychee`)

---

## Link Checking Configuration

CI and local checks share one config file — [`lychee.toml`](lychee.toml) — so they never drift.

| Setting | Default | Where to override |
|---|---|---|
| Request timeout | `15` s | `LINKCHECK_TIMEOUT` env var or `linkcheck_timeout` workflow input |
| Max concurrency | `8` requests | `LINKCHECK_CONCURRENCY` env var or `linkcheck_concurrency` workflow input |
| Lychee cache location | `.lycheecache` (repo root) | `LINKCHECK_CACHE_DIR` env var or `cache_dir` workflow input |
| Cache age | `1d` | `lychee.toml` (`max_cache_age`) |
| Accepted status codes | `200, 204, 401, 403` | `lychee.toml` (`accept`) |
| Excluded domains | twitter/x, linkedin, youtube, medium, amazon, amzn.to, web.archive.org | `lychee.toml` (`exclude`) |

### Quality gate

CI fails **only** on these categories (configurable via the `QUALITY_GATE_CATEGORIES` env var):

- `BROKEN_NOT_FOUND` (HTTP 404/410)
- `BROKEN_INTERNAL_FILE` (missing local file referenced from markdown)
- `TIMEOUT_OR_DNS_FAILURE`
- `HTTP_5XX`

`REDIRECTED` and `BOT_PROTECTED_OR_AUTH` links are reported as non-blocking warnings (annotations only).

### Run locally

```bash
chmod +x scripts/lint-and-check.sh
./scripts/lint-and-check.sh

# Or with overrides
LINKCHECK_TIMEOUT=30 LINKCHECK_CONCURRENCY=4 ./scripts/lint-and-check.sh
```
