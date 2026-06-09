#!/usr/bin/env python3
"""Enforce the 500-LOC rule. A file past the limit is a refactor signal."""
from __future__ import annotations

from pathlib import Path

LIMIT = 500
SUFFIXES = {".py", ".css", ".js", ".html"}
ROOTS = ("src", "tests", "governance")


def main() -> int:
    repo = Path(__file__).resolve().parents[2]
    offenders = []
    for root_name in ROOTS:
        root = repo / root_name
        if not root.exists():
            continue
        for f in root.rglob("*"):
            if f.is_file() and f.suffix in SUFFIXES:
                n = sum(1 for _ in f.open(encoding="utf-8"))
                if n > LIMIT:
                    offenders.append((f.relative_to(repo), n))
    for f, n in offenders:
        print(f"OVER {LIMIT} LOC ({n}): {f}")
    if offenders:
        print(f"\n{len(offenders)} file(s) exceed {LIMIT} lines. Split them.")
        return 1
    print(f"OK: all files within {LIMIT} LOC.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
