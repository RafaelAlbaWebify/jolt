"""Profile JOLT export/market operations directly with a read-only SQLite connection.

Usage: from the repository checkout, run tools/profile-jolt-runtime.ps1.
No HTTP server or backend logs required.
"""
from __future__ import annotations

import argparse
import cProfile
import io
import json
import os
import pstats
import sqlite3
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

TASKS = ("market", "review", "unified")


def _factory(db_path: Path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    def connect():
        connection = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True, timeout=5)
        connection.execute("PRAGMA query_only=ON")
        return connection

    engine = create_engine("sqlite://", creator=connect)
    return engine, Session


def _execute_task(db_path: Path, task: str) -> dict[str, object]:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "backend" / "src"))
    engine, session_type = _factory(db_path)
    profiler = cProfile.Profile()
    start = time.perf_counter()
    result: dict[str, object] = {"task": task}
    try:
        with session_type(engine) as session:
            profiler.enable()
            try:
                if task == "market":
                    from jolt.market_intelligence import build_market_intelligence

                    output = build_market_intelligence(session)
                    result["result_summary"] = {
                        "total_unique_roles": output.get("total_unique_roles")
                    }
                elif task == "review":
                    from jolt.review_inbox_exchange import build_review_inbox_exchange_json

                    output = build_review_inbox_exchange_json(session)
                    result["result_summary"] = {"output_bytes": len(output)}
                elif task == "unified":
                    from jolt.unified_ai_work_package import build_unified_ai_work_package_json

                    output = build_unified_ai_work_package_json(session)
                    result["result_summary"] = {"output_bytes": len(output)}
                else:
                    raise ValueError("Unknown task")
            finally:
                profiler.disable()
        result["state"] = "passed"
    except Exception as exc:
        result["state"] = "failed"
        result["error_type"] = type(exc).__name__
    finally:
        result["elapsed_seconds"] = round(time.perf_counter() - start, 3)
        stats = pstats.Stats(profiler)
        stats.sort_stats("cumulative")
        # Only function names, source file basenames and timings: never args or raw values.
        slow = []
        for (filename, line, function), (
            calls,
            _primitive_calls,
            own_seconds,
            total_seconds,
            _callers,
        ) in sorted(stats.stats.items(), key=lambda pair: pair[1][3], reverse=True):
            if function.startswith("<") and function != "<listcomp>":
                continue
            slow.append(
                {
                    "module": Path(filename).name,
                    "function": function,
                    "line": line,
                    "calls": calls,
                    "self_seconds": round(own_seconds, 3),
                    "total_seconds": round(total_seconds, 3),
                }
            )
            if len(slow) >= 25:
                break
        result["hotspots"] = slow
        engine.dispose()
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--task", choices=TASKS)
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args()
    database = args.db.resolve()
    if not database.is_file():
        parser.error("Database not found")
    if args.task:
        print(json.dumps(_execute_task(database, args.task)), flush=True)
        return
    if args.output is None:
        parser.error("--output is required")
    results = []
    for task in TASKS:
        started = time.perf_counter()
        try:
            worker = subprocess.run(
                [
                    sys.executable, str(Path(__file__).resolve()), "--db",
                    str(database), "--task", task,
                ],
                capture_output=True,
                text=True,
                timeout=args.timeout,
                check=False,
            )
            if worker.returncode:
                results.append({
                    "task": task, "state": "failed",
                    "error_type": "WorkerExited", "exit_code": worker.returncode,
                })
            else:
                results.append(json.loads(worker.stdout.strip().splitlines()[-1]))
        except subprocess.TimeoutExpired:
            results.append({
                "task": task, "state": "timeout",
                "elapsed_seconds": round(time.perf_counter() - started, 3),
            })
        except (ValueError, IndexError, json.JSONDecodeError):
            results.append({"task": task, "state": "failed", "error_type": "MissingResult"})
        print(task, results[-1]["state"], flush=True)
    report = {
        "contract": "jolt_direct_readonly_profile",
        "created_at": datetime.now(UTC).isoformat(),
        "database_bytes": database.stat().st_size,
        "tasks": results,
        "limitations": [
            "Direct Python function execution, not HTTP/UX wall-clock performance",
            "cProfile introduces profiling overhead",
            "SQLite opened in read-only mode; no DB writes permitted",
            "Only numeric timings, function names and summaries retained",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(args.output, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("jolt_direct_profile.json", json.dumps(report, indent=2))
    print("Profile ZIP:", args.output, flush=True)


if __name__ == "__main__":
    main()
