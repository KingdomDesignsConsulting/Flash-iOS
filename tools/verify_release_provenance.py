#!/usr/bin/env python3
"""Offline provenance/rollback-package validator. Never discovers or controls processes.

The authorized deployment operator supplies a JSON manifest and pre-captured
backups. This script only reads the exact paths explicitly listed therein.
It does not create backups, inspect the running service, or deploy anything.
"""
import argparse
import hashlib
import json
from pathlib import Path

REQUIRED = ("source_commit", "release_commit", "launcher_owner", "launcher_definition",
            "installed_executable", "startup_argv", "startup_environment",
            "runtime_dependencies", "model_identity", "cache_backups",
            "rollback_argv", "rollback_environment", "rollback_test_plan")
SHA = set("0123456789abcdef")


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def check_package(data):
    problems = []
    for field in REQUIRED:
        if field not in data or data[field] in ("", None, [], {}):
            problems.append(f"missing/empty {field}")
    if data.get("authorized_inventory") is not True:
        problems.append("authorized_inventory must be explicitly true")
    if not isinstance(data.get("startup_argv"), list) or not isinstance(data.get("rollback_argv"), list):
        problems.append("startup_argv and rollback_argv must be explicit argument arrays")
    if not isinstance(data.get("startup_environment"), dict) or not isinstance(data.get("rollback_environment"), dict):
        problems.append("startup_environment and rollback_environment must be explicit maps")
    if len(data.get("cache_backups", [])) != 2:
        problems.append("exactly two cache backup roots must be identified")
    files = data.get("files", [])
    if not files:
        problems.append("no verified artifact files supplied")
    for i, item in enumerate(files):
        path_text, claimed = item.get("path"), item.get("sha256")
        if not isinstance(path_text, str) or not Path(path_text).is_absolute():
            problems.append(f"files[{i}]: absolute file path required")
            continue
        if not isinstance(claimed, str) or len(claimed) != 64 or not set(claimed.lower()) <= SHA:
            problems.append(f"files[{i}]: valid sha256 required")
            continue
        path = Path(path_text)
        if not path.is_file():
            problems.append(f"files[{i}]: missing file")
            continue
        if digest(path) != claimed.lower():
            problems.append(f"files[{i}]: SHA256 mismatch")
    if data.get("release_commit") == data.get("source_commit") and not data.get("explain_same_source"):
        problems.append("release/source identical without explicit explanation")
    return problems


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", required=True, type=Path)
    args = p.parse_args()
    data = json.loads(args.manifest.read_text())
    failures = check_package(data)
    if failures:
        for f in failures:
            print("FAIL:", f)
        raise SystemExit(1)
    print("PASS: offline provenance package fields and listed artifact hashes; "
          "NOT production discovery, cache restore, launch mapping or rollback validation")


if __name__ == "__main__":
    main()
