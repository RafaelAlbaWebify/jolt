"""Read-only cross-language change-impact report for JOLT.

The analyzer intentionally distinguishes direct evidence from heuristic matches.
It does not execute repository code or mutate the checkout.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
from collections import defaultdict, deque
from pathlib import Path

SOURCE_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".ps1"}
IGNORED_PARTS = {".git", ".venv", "node_modules", "__pycache__", "dist", "build"}
CRITICAL = ("backend/src/jolt/database.py", "backend/src/jolt/schemas.py",
            "backend/src/jolt/main.py", "frontend/src/App.tsx")
DOMAIN_RULES = {
    "capture": (("capture", "discovery", "indeed", "linkedin", "infojobs", "jobgether", "supervised", "multipage"),
                ("backend/tests/test_live_capture_request_integrity.py",
                 "backend/tests/test_capture_evidence_chain_e2e.py",
                 "backend/tests/test_discovery_execution.py")),
    "applications": (("application", "workflow", "work_items"),
                     ("backend/tests/test_application_lifecycle_e2e.py",)),
    "ai_exchange": (("unified_ai", "ai_review", "ai_exchange", "review_inbox"),
                    ("backend/tests/test_unified_ai_work_package.py",)),
    "market": (("market_intelligence", "market_preparation"),
               ("backend/tests/test_market_intelligence_view.py",)),
    "persistence": (("database", "migration", "backup", "retention"),
                    ("backend/tests/test_migrations.py", "backend/tests/test_backup.py")),
}


def normalize(value: str) -> str:
    return value.replace("\\", "/").removeprefix("./")


def inventory(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*")
            if p.is_file() and p.suffix in SOURCE_EXTENSIONS
            and not (set(p.relative_to(root).parts) & IGNORED_PARTS)}


def python_imports(path: str, content: str, known: set[str]) -> set[str]:
    tree = ast.parse(content, filename=path)
    found: set[str] = set()
    for node in ast.walk(tree):
        candidates: list[str] = []
        if isinstance(node, ast.Import):
            candidates = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            base = ".".join(["jolt"] + path.removeprefix("backend/src/jolt/").removesuffix(".py").split("/")[:-1])
            if node.level:
                parent = base.split(".")
                candidates = [".".join(parent[:len(parent) - node.level + 1] + [node.module])]
            else:
                candidates = [node.module]
            candidates += [candidates[0] + "." + alias.name for alias in node.names]
        for name in candidates:
            if name == "jolt" or name.startswith("jolt."):
                target = "backend/src/" + name.replace(".", "/") + ".py"
                package = "backend/src/" + name.replace(".", "/") + "/__init__.py"
                if target in known:
                    found.add(target)
                elif package in known:
                    found.add(package)
    return found


def relative_js_target(path: str, spec: str, known: set[str]) -> str | None:
    if not spec.startswith("."):
        return None
    base = (Path(path).parent / spec).as_posix()
    # pathlib does not eliminate '..' in purely lexical paths
    parts = []
    for part in base.split("/"):
        if part == "..":
            if parts:
                parts.pop()
        elif part != ".":
            parts.append(part)
    base = "/".join(parts)
    for candidate in (base, *(base + ext for ext in (".ts", ".tsx", ".js", ".jsx")),
                      *(base + "/index" + ext for ext in (".ts", ".tsx", ".js"))):
        if candidate in known:
            return candidate
    return None


def edges(root: Path, known: set[str]) -> tuple[dict[str, set[str]], list[str]]:
    graph: dict[str, set[str]] = defaultdict(set)
    warnings = []
    for path in sorted(known):
        try:
            content = (root / path).read_text(encoding="utf-8-sig")
            if path.endswith(".py"):
                graph[path].update(python_imports(path, content, known))
            elif Path(path).suffix in {".ts", ".tsx", ".js", ".jsx"}:
                for match in re.finditer(r"""(?:from\s*|import\s*\(|require\s*\()\s*['"]([^'"]+)['"]""", content):
                    target = relative_js_target(path, match.group(1), known)
                    if target:
                        graph[path].add(target)
            elif path.endswith(".ps1"):
                # Matches explicit calls to sibling scripts, not dynamic Invoke-Expression.
                for match in re.finditer(r"""(?:\$PSScriptRoot|\.\\|\.\/)[\\/]*([\w.-]+\.ps1)""", content, re.I):
                    target = "tools/" + match.group(1)
                    if target in known and target != path:
                        graph[path].add(target)
        except (OSError, UnicodeError, SyntaxError) as exc:
            warnings.append(f"{path}: {type(exc).__name__}: {exc}")
    return graph, warnings


def git_changes(root: Path, base: str) -> list[str]:
    result = subprocess.run(["git", "-C", str(root), "diff", "--name-only", base, "--"],
                            capture_output=True, text=True, check=True)
    unstaged = subprocess.run(["git", "-C", str(root), "ls-files", "--others", "--exclude-standard"],
                              capture_output=True, text=True, check=True)
    return sorted({normalize(x) for x in (result.stdout + "\n" + unstaged.stdout).splitlines() if x.strip()})


def analyze(root: Path, changed: list[str]) -> dict:
    known = inventory(root)
    if not known:
        raise ValueError("empty source inventory")
    graph, warnings = edges(root, known)
    reverse: dict[str, set[str]] = defaultdict(set)
    for caller, dependencies in graph.items():
        for dependency in dependencies:
            reverse[dependency].add(caller)
    seen = set(changed)
    queue = deque((p, 0) for p in changed)
    distances = {}
    while queue:
        item, depth = queue.popleft()
        for parent in reverse.get(item, ()):
            if parent not in seen:
                seen.add(parent)
                distances[parent] = depth + 1
                queue.append((parent, depth + 1))
    tests = sorted(p for p in seen if "/tests/" in p or p.endswith(".test.tsx") or p.endswith(".test.ts"))
    domains = {}
    for name, (terms, required_tests) in DOMAIN_RULES.items():
        matched = sorted(p for p in seen if any(term in p.lower() for term in terms))
        if matched:
            domains[name] = {"affected_files": matched, "regression_candidates": list(required_tests),
                             "missing_candidates": [t for t in required_tests if t not in known]}
    # Affected main.py is a composition root and widely imported by tests.
    uncertain = ["Dynamic imports, HTTP route consumers, SQL relationships and runtime PowerShell commands are not fully resolved."]
    if any(p.startswith("frontend/") for p in seen):
        uncertain.append("React-to-FastAPI HTTP contract relationships require explicit integration tests.")
    if any(p.startswith("tools/") for p in seen):
        uncertain.append("PowerShell subprocess argument and encoding boundaries require runtime contract tests.")
    return {"contract": "jolt-change-impact-v1", "inventory_files": len(known),
            "resolved_edges": sum(map(len, graph.values())), "changed": changed,
            "affected_dependents": sorted(distances), "test_candidates": tests,
            "domains": domains, "warnings": warnings, "unresolved_relationships": uncertain,
            "critical_changed": sorted(set(changed) & set(CRITICAL))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--base", default="HEAD")
    parser.add_argument("--changed", nargs="*", help="Explicit paths; default: git diff plus untracked")
    parser.add_argument("--output", type=Path, help="Optional JSON report")
    args = parser.parse_args()
    root = args.root.resolve()
    if not (root / "backend/src/jolt").is_dir() or not (root / "frontend/src").is_dir():
        parser.error("invalid JOLT repository root")
    changed = [normalize(p) for p in args.changed] if args.changed is not None else git_changes(root, args.base)
    report = analyze(root, sorted(set(changed)))
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
