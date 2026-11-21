#!/usr/bin/env python3
"""Non-destructive code complexity and synthetic performance quality gate."""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTENSIONS = {".py", ".ts", ".tsx", ".ps1"}
SOURCE_ROOTS = ("backend/src/jolt/", "frontend/src/", "tools/")
SKIP_SUFFIXES = (".test.tsx", ".test.ts", ".spec.ts", ".spec.tsx")
WARN_FILE_LINES = 650
WARN_FUNCTION_LINES = 100
MAX_NEW_FILE_LINES = 650
MAX_NET_ADDED_LINES = 150


def tracked_sources() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True
    )
    return sorted(
        p.decode() for p in result.stdout.split(b"\0") if p
        if p.decode().startswith(SOURCE_ROOTS)
        and Path(p.decode()).suffix in EXTENSIONS
        and not p.decode().endswith(SKIP_SUFFIXES)
    )


def function_lengths(path: str, source: str) -> list[tuple[str, int]]:
    if not path.endswith(".py"):
        return []
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError:
        return [("<syntax-error>", len(source.splitlines()))]
    return [
        (node.name, node.end_lineno - node.lineno + 1)
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.end_lineno is not None
    ]


def inspect() -> dict:
    files = tracked_sources()
    large_files = []
    large_functions = []
    total_lines = 0
    for name in files:
        path = ROOT / name
        if not path.is_file():
            continue
        source = path.read_text(encoding="utf-8-sig")
        lines = len(source.splitlines())
        total_lines += lines
        if lines > WARN_FILE_LINES:
            large_files.append({"path": name, "lines": lines})
        for func, count in function_lengths(name, source):
            if count > WARN_FUNCTION_LINES:
                large_functions.append({"path": name, "function": func, "lines": count})
    return {
        "tracked_source_files": len(files),
        "source_lines": total_lines,
        "large_files": sorted(large_files, key=lambda x: -x["lines"]),
        "large_python_functions": sorted(large_functions, key=lambda x: -x["lines"]),
    }


def changed_files(base: str) -> tuple[list[dict], list[str]]:
    # Compare against the merge-base to avoid assessing unrelated branch history.
    base_commit = subprocess.check_output(
        ["git", "merge-base", base, "HEAD"], cwd=ROOT, text=True
    ).strip()
    raw = subprocess.check_output(
        ["git", "diff", "--numstat", "--diff-filter=ACMR", base_commit, "HEAD"],
        cwd=ROOT, text=True
    )
    rows = []
    violations = []
    for line in raw.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3 or not parts[0].isdigit() or not parts[1].isdigit():
            continue
        added, removed, path = int(parts[0]), int(parts[1]), parts[2]
        if not path.startswith(SOURCE_ROOTS) or Path(path).suffix not in EXTENSIONS:
            continue
        net = added - removed
        rows.append({"path": path, "added": added, "removed": removed, "net": net})
        if net > MAX_NET_ADDED_LINES:
            violations.append(f"{path}: net growth {net} > {MAX_NET_ADDED_LINES}")
    new_paths = subprocess.check_output(
        ["git", "diff", "--name-only", "--diff-filter=A", base_commit, "HEAD"],
        cwd=ROOT, text=True
    ).splitlines()
    for path in new_paths:
        if not path.startswith(SOURCE_ROOTS) or Path(path).suffix not in EXTENSIONS:
            continue
        candidate = ROOT / path
        if candidate.is_file() and len(candidate.read_text(encoding="utf-8-sig").splitlines()) > MAX_NEW_FILE_LINES:
            violations.append(f"{path}: new file exceeds {MAX_NEW_FILE_LINES} lines")
    return rows, violations


def benchmark(rounds: int = 7) -> dict:
    # Deliberately synthetic: validates local serialization cost, not browser/network throughput.
    payload = [
        {"id": str(i), "title": "Support Engineer", "source": "indeed",
         "description": "Troubleshooting applications and incidents. " * 25}
        for i in range(400)
    ]
    measurements = []
    for _ in range(rounds):
        start = time.perf_counter()
        encoded = json.dumps(payload, ensure_ascii=False)
        decoded = json.loads(encoded)
        duration = (time.perf_counter() - start) * 1000
        assert len(decoded) == 400
        measurements.append(duration)
    measurements.sort()
    return {
        "fixture_items": 400,
        "encoded_bytes": len(encoded.encode("utf-8")),
        "median_roundtrip_ms": round(measurements[len(measurements) // 2], 3),
        "max_roundtrip_ms": round(max(measurements), 3),
        "scope": "synthetic JSON serialization only; not a JOLT capture benchmark",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", help="Git ref for no-regression growth comparison")
    parser.add_argument("--output", help="Optional JSON report path")
    parser.add_argument("--strict", action="store_true", help="Fail on growth violations")
    args = parser.parse_args()
    report = {"complexity": inspect(), "performance_smoke": benchmark()}
    violations = []
    if args.base:
        report["changes"], violations = changed_files(args.base)
    report["growth_violations"] = violations
    report["result"] = "fail" if args.strict and violations else "pass"
    output = json.dumps(report, indent=2, ensure_ascii=False)
    print(output)
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(output + "\n", encoding="utf-8")
    if violations:
        print("Growth violations: " + "; ".join(violations), file=sys.stderr)
    return 1 if args.strict and violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
