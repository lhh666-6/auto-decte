#!/usr/bin/env python3
"""Fail CI when the Web transformation changes frozen mobile sources."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MOBILE_PREFIX = "frontend/apps/web/src/mobile/"


def mobile_changes(paths: Iterable[str]) -> set[str]:
    """Return normalized paths inside the frozen mobile source directory."""
    normalized = {path.replace("\\", "/").removeprefix("./") for path in paths}
    return {path for path in normalized if path.startswith(MOBILE_PREFIX)}


def git_changed_paths(base: str, head: str) -> list[str]:
    """Return paths changed between two refs, failing closed on Git errors."""
    result = subprocess.run(
        ["git", "diff", "--name-only", base, head, "--", MOBILE_PREFIX],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or f"git exited with {result.returncode}"
        raise RuntimeError(detail)
    return [line for line in result.stdout.splitlines() if line]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reject changes under frontend/apps/web/src/mobile/"
    )
    parser.add_argument("--base", default="HEAD", help="base Git ref")
    parser.add_argument("--head", default="HEAD", help="head Git ref")
    args = parser.parse_args()

    try:
        violations = mobile_changes(git_changed_paths(args.base, args.head))
    except (OSError, RuntimeError) as exc:
        print(f"Mobile boundary check failed: {exc}", file=sys.stderr)
        return 2

    if not violations:
        print(f"Mobile boundary check passed ({args.base}..{args.head})")
        return 0

    print("Mobile boundary violation:", file=sys.stderr)
    for path in sorted(violations):
        print(f"  - {path}", file=sys.stderr)
    print(
        "Web transformation work must not modify "
        "frontend/apps/web/src/mobile/**.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
