from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any


CORE_TABLES = (
    "source_documents",
    "postings",
    "evaluations",
    "review_decisions",
    "applications",
    "application_events",
    "application_tasks",
    "application_interviews",
    "application_contacts",
    "application_documents",
    "outcomes",
    "capture_runs",
    "capture_pages",
    "capture_items",
    "capture_artifacts",
    "professional_capture_runs",
    "professional_capture_artifacts",
)

WATCHED_TABLES = {
    "source_documents",
    "postings",
    "evaluations",
    "review_decisions",
    "applications",
    "outcomes",
    "capture_runs",
    "capture_pages",
    "capture_items",
    "capture_artifacts",
    "professional_capture_runs",
    "professional_capture_artifacts",
}


def default_db_path() -> Path:
    return Path(__file__).resolve().parents[1] / "backend" / "data" / "jolt.db"


def table_names(connection: sqlite3.Connection) -> list[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [str(row[0]) for row in rows]


def count_rows(connection: sqlite3.Connection, table: str) -> int:
    try:
        row = connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()
    except sqlite3.DatabaseError:
        return -1
    return int(row[0] or 0) if row else 0


def foreign_keys_for_table(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    rows = connection.execute(f'PRAGMA foreign_key_list("{table}")').fetchall()
    keys: list[dict[str, Any]] = []
    for row in rows:
        keys.append(
            {
                "from_table": table,
                "id": row[0],
                "seq": row[1],
                "to_table": row[2],
                "from_column": row[3],
                "to_column": row[4],
                "on_update": row[5],
                "on_delete": row[6],
                "match": row[7],
            }
        )
    return keys


def indexes_for_table(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    indexes: list[dict[str, Any]] = []
    for row in connection.execute(f'PRAGMA index_list("{table}")').fetchall():
        index_name = row[1]
        columns = [info[2] for info in connection.execute(f'PRAGMA index_info("{index_name}")').fetchall()]
        indexes.append(
            {
                "table": table,
                "index": index_name,
                "unique": bool(row[2]),
                "origin": row[3],
                "partial": bool(row[4]),
                "columns": columns,
            }
        )
    return indexes


def sample_references(connection: sqlite3.Connection, fk: dict[str, Any], limit: int) -> dict[str, Any]:
    from_table = fk["from_table"]
    from_column = fk["from_column"]
    to_table = fk["to_table"]
    to_column = fk["to_column"]
    total = count_rows(connection, from_table)
    try:
        non_null = connection.execute(
            f'SELECT COUNT(*) FROM "{from_table}" WHERE "{from_column}" IS NOT NULL'
        ).fetchone()[0]
        missing_parent = connection.execute(
            f'''
            SELECT COUNT(*)
            FROM "{from_table}" child
            LEFT JOIN "{to_table}" parent ON parent."{to_column}" = child."{from_column}"
            WHERE child."{from_column}" IS NOT NULL AND parent."{to_column}" IS NULL
            '''
        ).fetchone()[0]
        samples = [
            dict(row)
            for row in connection.execute(
                f'''
                SELECT child."{from_column}" AS referenced_value, COUNT(*) AS child_rows
                FROM "{from_table}" child
                WHERE child."{from_column}" IS NOT NULL
                GROUP BY child."{from_column}"
                ORDER BY child_rows DESC
                LIMIT ?
                ''',
                (limit,),
            ).fetchall()
        ]
    except sqlite3.DatabaseError as exc:
        return {"error": str(exc), "from_table_row_count": total}
    return {
        "from_table_row_count": total,
        "non_null_reference_count": int(non_null or 0),
        "missing_parent_count": int(missing_parent or 0),
        "top_referenced_values": samples,
    }


def audit_database(db_path: Path, sample_limit: int) -> dict[str, Any]:
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    try:
        tables = table_names(connection)
        table_counts = {table: count_rows(connection, table) for table in tables}
        outbound_fks: list[dict[str, Any]] = []
        indexes: list[dict[str, Any]] = []
        for table in tables:
            outbound_fks.extend(foreign_keys_for_table(connection, table))
            indexes.extend(indexes_for_table(connection, table))

        inbound_by_table: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for fk in outbound_fks:
            inbound_by_table[fk["to_table"]].append(fk)

        watched_inbound = {
            table: inbound_by_table.get(table, [])
            for table in sorted(WATCHED_TABLES | set(CORE_TABLES))
            if table in tables or table in inbound_by_table
        }
        reference_samples = [
            {
                **fk,
                "reference_sample": sample_references(connection, fk, sample_limit),
            }
            for fk in outbound_fks
            if fk["to_table"] in WATCHED_TABLES or fk["from_table"] in WATCHED_TABLES
        ]
        delete_risk = []
        for table, inbound in watched_inbound.items():
            if not inbound:
                continue
            delete_risk.append(
                {
                    "table": table,
                    "row_count": table_counts.get(table),
                    "referenced_by": [
                        {
                            "from_table": fk["from_table"],
                            "from_column": fk["from_column"],
                            "to_column": fk["to_column"],
                            "on_delete": fk["on_delete"],
                            "child_row_count": table_counts.get(fk["from_table"]),
                        }
                        for fk in inbound
                    ],
                }
            )
        return {
            "db_path": str(db_path),
            "table_counts": table_counts,
            "foreign_keys": outbound_fks,
            "inbound_references_for_core_tables": watched_inbound,
            "delete_risk_summary": delete_risk,
            "indexes": indexes,
            "reference_samples": reference_samples,
        }
    finally:
        connection.close()


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def flatten_delete_risk(summary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in summary:
        for reference in item["referenced_by"]:
            rows.append({"table": item["table"], "row_count": item["row_count"], **reference})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit the JOLT SQLite schema, foreign-key graph, and delete risks."
    )
    parser.add_argument("--db", type=Path, default=default_db_path())
    parser.add_argument("--output-dir", type=Path, default=Path.home() / "Downloads" / "JOLT_SCHEMA_FK_AUDIT")
    parser.add_argument("--sample-limit", type=int, default=10)
    args = parser.parse_args()

    db_path = args.db.resolve()
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = audit_database(db_path, args.sample_limit)
    json_path = output_dir / "jolt_schema_fk_audit.json"
    risk_csv_path = output_dir / "jolt_schema_delete_risk.csv"
    fk_csv_path = output_dir / "jolt_schema_foreign_keys.csv"
    counts_csv_path = output_dir / "jolt_schema_table_counts.csv"

    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    write_csv(risk_csv_path, flatten_delete_risk(payload["delete_risk_summary"]))
    write_csv(fk_csv_path, payload["foreign_keys"])
    write_csv(
        counts_csv_path,
        [{"table": table, "row_count": count} for table, count in payload["table_counts"].items()],
    )

    print(json.dumps({
        "db_path": payload["db_path"],
        "table_count": len(payload["table_counts"]),
        "foreign_key_count": len(payload["foreign_keys"]),
        "delete_risk_count": len(payload["delete_risk_summary"]),
        "top_delete_risks": payload["delete_risk_summary"][:12],
        "wrote": [str(json_path), str(risk_csv_path), str(fk_csv_path), str(counts_csv_path)],
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
