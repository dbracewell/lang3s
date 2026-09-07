#!/usr/bin/env python3
"""Fail CI when pip-audit finds vulns outside an allowlist."""

from __future__ import annotations

import json
import pathlib
import sys

ALLOWLIST_PATH = pathlib.Path(".github/security/pip-audit-allowlist.txt")
REPORT_PATH = pathlib.Path("backend/pip-audit-report.json")


def load_allowlist(path: pathlib.Path) -> set[str]:
    if not path.exists():
        return set()
    packages: set[str] = set()
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        packages.add(line.lower())
    return packages


def main() -> int:
    allowlist = load_allowlist(ALLOWLIST_PATH)
    report = json.loads(REPORT_PATH.read_text())

    violations: list[tuple[str, str]] = []
    allowlisted_counts: dict[str, int] = {}

    for dep in report.get("dependencies", []):
        pkg = dep.get("name", "").lower()
        vulns = dep.get("vulns", [])
        if not vulns:
            continue

        if pkg in allowlist:
            allowlisted_counts[pkg] = allowlisted_counts.get(pkg, 0) + len(vulns)
            continue

        for vuln in vulns:
            vid = vuln.get("id", "UNKNOWN")
            violations.append((pkg, vid))

    if allowlisted_counts:
        print("Allowlisted vulnerabilities:")
        for pkg, count in sorted(allowlisted_counts.items()):
            print(f"  - {pkg}: {count}")

    if violations:
        print("\nDisallowed vulnerabilities found:")
        for pkg, vid in violations:
            print(f"  - {pkg}: {vid}")
        return 1

    print("No disallowed vulnerabilities found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
