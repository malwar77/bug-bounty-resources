#!/usr/bin/env python3
"""Validates lychee.toml against an explicit schema and verifies category/status values.

Exits with code 1 and a detailed error message if validation fails.
"""
import os
import sys

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

ALLOWED_KEYS = {
    "timeout": int,
    "max_concurrency": int,
    "accept": list,
    "cache": bool,
    "max_cache_age": str,
    "exclude_mail": bool,
    "exclude": list,
}

VALID_CATEGORIES = {
    "BROKEN_NOT_FOUND",
    "BROKEN_INTERNAL_FILE",
    "TIMEOUT_OR_DNS_FAILURE",
    "HTTP_5XX",
    "HTTP_4XX",
    "REDIRECTED",
    "BOT_PROTECTED_OR_AUTH",
    "PASSED",
    "PASSED_EXCLUDED",
}


def validate_config(config_path="lychee.toml"):
    if not os.path.exists(config_path):
        print(f"Error: Config file not found at '{config_path}'", file=sys.stderr)
        return False

    with open(config_path, "rb") as f:
        try:
            data = tomllib.load(f)
        except Exception as e:
            print(f"Syntax error in TOML file '{config_path}': {e}", file=sys.stderr)
            return False

    errors = []

    # Check for unsupported keys
    for k in data.keys():
        if k not in ALLOWED_KEYS:
            errors.append(f"Unsupported key in {config_path}: '{k}'. Allowed keys: {sorted(ALLOWED_KEYS.keys())}")

    # Validate types and ranges
    for k, expected_type in ALLOWED_KEYS.items():
        if k in data:
            val = data[k]
            if not isinstance(val, expected_type):
                errors.append(f"Invalid type for key '{k}': expected {expected_type.__name__}, got {type(val).__name__}")
                continue

            if k in ("timeout", "max_concurrency") and val <= 0:
                errors.append(f"Key '{k}' must be a positive integer, got {val}")

            if k == "accept":
                for code in val:
                    if not isinstance(code, int) or code < 100 or code > 599:
                        errors.append(f"Invalid HTTP status code in 'accept': {code}. Must be integer between 100 and 599")

            if k == "exclude":
                for pat in val:
                    if not isinstance(pat, str):
                        errors.append(f"Invalid exclude pattern: {pat}. Must be a string")

    # Validate quality gate environment variables if set
    qg_env = os.environ.get("QUALITY_GATE_CATEGORIES")
    if qg_env:
        for cat in [c.strip() for c in qg_env.split(",") if c.strip()]:
            if cat not in VALID_CATEGORIES:
                errors.append(f"Unknown category in QUALITY_GATE_CATEGORIES: '{cat}'. Valid categories: {sorted(VALID_CATEGORIES)}")

    warn_env = os.environ.get("WARNING_CATEGORIES")
    if warn_env:
        for cat in [c.strip() for c in warn_env.split(",") if c.strip()]:
            if cat not in VALID_CATEGORIES:
                errors.append(f"Unknown category in WARNING_CATEGORIES: '{cat}'. Valid categories: {sorted(VALID_CATEGORIES)}")

    if errors:
        print(f"FAILED: {len(errors)} validation error(s) found in {config_path}:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return False

    print(f"SUCCESS: {config_path} passed all schema and value validation checks.")
    return True


if __name__ == "__main__":
    cfg_file = sys.argv[1] if len(sys.argv) > 1 else "lychee.toml"
    if not validate_config(cfg_file):
        sys.exit(1)
