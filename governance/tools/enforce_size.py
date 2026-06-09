#!/usr/bin/env python3
"""Enforce the 500-LOC rule. A file past the limit is a refactor signal."""
from __future__ import annotations
import sys
from pathlib import Path

LIMIT = 500


def main() -> int:
    root = Path(__file__).resolve().parents[2] / "src"
    offenders = []
    for f in root.rglob("*.py"):
        n = sum(1 for _ in f.open(encoding="utf-8"))
        if n > LIMIT:
            offenders.append((f, n))
    for f, n in offenders:
        print(f"OVER {LIMIT} LOC ({n}): {f}")
    if offenders:
        print(f"\n{len(offenders)} file(s) exceed {LIMIT} lines. Split them.")
        return 1
    print(f"OK: all files within {LIMIT} LOC.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
