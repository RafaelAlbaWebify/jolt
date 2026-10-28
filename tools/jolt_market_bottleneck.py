"""Bounded, read-only Market Insights phase profiler with timeout-safe checkpoints."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from functools import wraps
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

PHASES = (
    "_durable_capture_market_records",
    "_manual_market_postings",
    "_effective_evaluations",
    "_filter_by_timeframe",
    "_deduplicate_market_postings",
    "group_semantic_duplicates",
    "_scope_data",
    "_learning_refresh_status",
)


def _worker(database: Path) -> None:
    from jolt_direct_profile import _factory

    backend_src = Path(__file__).resolve().parents[1] / "backend" / "src"
    sys.path.insert(0, str(backend_src))
    import jolt.market_intelligence as market

    engine, session_type = _factory(database)
    started = time.perf_counter()

    def emit(stage: str, event: str, seconds: float | None = None) -> None:
        payload = {"stage": stage, "event": event, "at_seconds": round(time.perf_counter() - started, 3)}
        if seconds is not None:
            payload["duration_seconds"] = round(seconds, 3)
        print(json.dumps(payload, separators=(",", ":")), flush=True)

    for name in PHASES:
        original = getattr(market, name)

        def instrument(func, stage):
            @wraps(func)
            def wrapped(*args, **kwargs):
                emit(stage, "start")
                begun = time.perf_counter()
                try:
                    return func(*args, **kwargs)
                finally:
                    emit(stage, "finish", time.perf_counter() - begun)
            return wrapped

        setattr(market, name, instrument(original, name))

    try:
        emit("build_market_intelligence", "start")
        with session_type(engine) as session:
            market.build_market_intelligence(session)
        emit("build_market_intelligence", "finish", time.perf_counter() - started)
    except Exception as exc:
        emit("build_market_intelligence", "failed")
        print(json.dumps({"error_type": type(exc).__name__}), flush=True)
    finally:
        engine.dispose()


def _decode_lines(stdout: str | bytes | None) -> list[dict[str, object]]:
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")
    events = []
    for line in (stdout or "").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and isinstance(value.get("stage"), str):
            events.append(value)
    return events[-100:]


def run(database: Path, output: Path, timeout: int) -> dict[str, object]:
    command = [sys.executable, str(Path(__file__).resolve()), "--worker", "--db", str(database)]
    started = time.perf_counter()
    try:
        process = subprocess.run(command, capture_output=True, timeout=timeout, check=False)
        events = _decode_lines(process.stdout)
        state = "passed" if process.returncode == 0 and any(
            e.get("stage") == "build_market_intelligence" and e.get("event") == "finish"
            for e in events
        ) else "failed"
    except subprocess.TimeoutExpired as exc:
        events = _decode_lines(exc.stdout)
        state = "timeout"
    active = {}
    for event in events:
        stage = str(event["stage"])
        if event.get("event") == "start":
            active[stage] = event["at_seconds"]
        elif event.get("event") == "finish":
            active.pop(stage, None)
    report = {
        "contract": "jolt_market_phase_profile",
        "generated_at": datetime.now(UTC).isoformat(),
        "state": state,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "timeout_seconds": timeout,
        "database_bytes": database.stat().st_size,
        "active_at_exit": list(active),
        "events": events,
        "limitations": [
            "SQL database opened read-only, query_only=ON",
            "Stage wall timings include nested stages; do not sum them",
            "Only stage identifiers/times exported; no job or applicant content",
            "Child may be terminated at timeout, last completed checkpoint remains",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as z:
        z.writestr("jolt_market_profile.json", json.dumps(report, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    database = args.db.resolve()
    if not database.is_file():
        parser.error("Database not found")
    if args.worker:
        _worker(database)
        return
    if args.output is None or not 5 <= args.timeout <= 300:
        parser.error("--output required and --timeout must be between 5 and 300")
    report = run(database, args.output, args.timeout)
    print("State:", report["state"])
    print("Active at exit:", ", ".join(report["active_at_exit"]) or "none")
    print("ZIP:", args.output)


if __name__ == "__main__":
    main()
