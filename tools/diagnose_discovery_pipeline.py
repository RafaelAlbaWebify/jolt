#!/usr/bin/env python3
"""Read-only static discovery-pipeline diagnosis. Never starts portals or opens a DB."""
from __future__ import annotations

import argparse
import ast
from collections import defaultdict, deque
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import subprocess

PORTALS = ("linkedin", "indeed", "infojobs", "jobgether")
STAGES = {
    "search": ("saved_search", "search_portfolio", "discovery_batch", "discovery_queue"),
    "capture": ("capture", "playwright", "browser"),
    "ingestion": ("ingest", "intake", "source_document", "capture_workflow"),
    "deduplication": ("duplicate", "canonical", "identity", "content_hash"),
    "review": ("review", "opportunity_index", "evaluation", "readiness"),
}
RISK_TERMS = {
    "description": r"\bdescription\b",
    "source_identity": r"source_job_id|canonical_url|source_url",
    "provenance": r"provenance|source_document|capture_artifact",
    "retry": r"retry|backoff|attempts?",
    "persistence": r"session\.(?:add|commit|flush)|sqlite|ingest_capture",
}


def tracked(root: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"], capture_output=True, check=True
    )
    return sorted(
        p.decode("utf-8") for p in proc.stdout.split(b"\0") if p
    )


def inspect(root: Path, paths: list[str]) -> dict:
    modules = {}
    errors = []
    for path in paths:
        if not path.startswith("backend/src/jolt/") or not path.endswith(".py"):
            continue
        name = path.removeprefix("backend/src/").removesuffix(".py").replace("/", ".")
        try:
            source = (root / path).read_text(encoding="utf-8")
            tree = ast.parse(source, filename=path)
        except (OSError, UnicodeError, SyntaxError) as exc:
            errors.append({"path": path, "error": str(exc)})
            continue
        imports, symbols = set(), []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("jolt"):
                imports.add(node.module)
            elif isinstance(node, ast.Import):
                imports.update(a.name for a in node.names if a.name.startswith("jolt"))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.col_offset == 0:
                symbols.append({"name": node.name, "line": node.lineno})
        modules[name] = {
            "path": path,
            "lines": len(source.splitlines()),
            "imports": sorted(imports),
            "symbols": symbols,
            "risk_signals": sorted(k for k, pat in RISK_TERMS.items() if re.search(pat, source, re.I)),
        }
    return {"modules": modules, "parse_errors": errors}


def build_report(root: Path) -> dict:
    paths = tracked(root)
    inspected = inspect(root, paths)
    mods = inspected["modules"]
    graph = {
        name: sorted(i for i in d["imports"] if i in mods and i != name)
        for name, d in mods.items()
    }
    reverse = defaultdict(set)
    for name, imports in graph.items():
        for imp in imports:
            reverse[imp].add(name)

    # Locate portal code by filenames and symbols, not by assuming module names.
    portal_inventory = {}
    for portal in PORTALS:
        relevant = sorted(
            path for path in paths
            if portal in path.casefold()
            and (path.endswith((".py", ".ps1", ".ts", ".tsx")) or "/tests/" in path)
        )
        backend = [name for name, v in mods.items() if portal in name or portal in v["path"]]
        portal_inventory[portal] = {
            "named_files": relevant,
            "backend_modules": backend,
            "has_source_named_tests": any("/test" in p or ".test." in p for p in relevant),
            "runtime_portal_verified": False,
            "runtime_evidence": "NOT_EXECUTED",
        }

    # Bounded direct import reachability to shared persistence/index modules.
    targets = sorted(name for name in mods if any(
        term in name for term in ("capture_ingestion", "capture_workflow", "opportunity_index", "database")
    ))
    def shortest(start: str, target: str) -> list[str] | None:
        q = deque([(start, [start])])
        visited = {start}
        while q:
            node, chain = q.popleft()
            if node == target:
                return chain
            for child in graph.get(node, []):
                if child not in visited:
                    visited.add(child)
                    q.append((child, chain + [child]))
        return None

    for portal, info in portal_inventory.items():
        info["static_import_paths_to_shared_modules"] = [
            {"from": start, "to": target, "modules": chain}
            for start in info["backend_modules"] for target in targets
            if (chain := shortest(start, target)) is not None
        ]

    stage_modules = {
        stage: sorted(name for name, data in mods.items()
                      if any(word in name or any(word in symbol["name"].casefold()
                                                for symbol in data["symbols"])
                             for word in words))
        for stage, words in STAGES.items()
    }
    entrypoints = {
        "backend_routes": [
            {"module": n, "path": data["path"], "line": sym["line"], "name": sym["name"]}
            for n, data in mods.items()
            for sym in data["symbols"]
            if n.endswith(".main") and any(term in sym["name"].lower()
                                          for term in ("capture", "discovery", "search", "opportunity", "review"))
        ],
        "frontend_candidates": sorted(p for p in paths if p.startswith("frontend/src/")
                                      and p.endswith((".tsx", ".ts"))
                                      and re.search(r"discovery|capture|opportunity|linkedin|indeed|infojobs|jobgether|search", p, re.I)),
    }
    test_paths = sorted(p for p in paths if (
        p.startswith("backend/tests/") and p.endswith(".py")
        or p.startswith("frontend/src/") and ".test." in p
    ))
    return {
        "schema_version": 1,
        "generated_utc": datetime.now(UTC).isoformat(),
        "scope": "STATIC_SOURCE_ONLY",
        "safety": {"database_opened": False, "portals_contacted": False, "capture_executed": False,
                   "no_operator_data_mutation": True},
        "repo": str(root),
        "tracked_file_count": len(paths),
        "python_module_count": len(mods),
        "portal_inventory": portal_inventory,
        "stage_modules": stage_modules,
        "entrypoints": entrypoints,
        "shared_targets": targets,
        "shared_module_dependents": {name: sorted(reverse.get(name, [])) for name in targets},
        "test_candidates": test_paths,
        "parse_errors": inspected["parse_errors"],
        "modules": mods,
        "unverified_questions": [
            "Does a real bounded capture complete for each portal in the operator's authenticated Windows session?",
            "Are full description, URL, source job identity and capture provenance preserved across ingestion?",
            "Do retries terminate with truthful states, and are duplicates prevented without overwriting decisions?",
            "Does a captured job appear in Review Inbox and survive restart?",
            "How much operator time and intervention does an accepted opportunity require?",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    root = args.root.resolve()
    report = build_report(root)
    output = args.output or root / ".jolt" / "diagnostics" / "discovery-architecture.json"
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "report": str(output), "scope": report["scope"],
        "tracked_files": report["tracked_file_count"],
        "python_modules": report["python_module_count"],
        "portal_named_files": {p: len(x["named_files"]) for p, x in report["portal_inventory"].items()},
        "parse_errors": len(report["parse_errors"]),
        "real_portal_acceptance": "NOT_EXECUTED",
    }, indent=2))
    return 1 if report["parse_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
