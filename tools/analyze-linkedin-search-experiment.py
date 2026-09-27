from __future__ import annotations

import argparse
import json
import re
import sqlite3
import statistics
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

POSITIVE_INTERNATIONAL = re.compile(
    r"\b(worldwide|anywhere|global remote|remote globally|emea|europe(?:an)?|"
    r"european union|\beu\b|spain|cet|gmt|utc|contractor|independent contractor|"
    r"\bb2b\b|employer of record|\beor\b|deel|remote\.com|follow[- ]the[- ]sun)\b",
    re.IGNORECASE,
)
RESTRICTIVE_INTERNATIONAL = re.compile(
    r"\b(us only|u\.s\. only|united states only|must reside in (?:the )?u\.s\.|"
    r"must reside in (?:the )?united states|us work authorization|required to work in the us|"
    r"no sponsorship|canada only|australia only|must reside in canada|must reside in australia)\b",
    re.IGNORECASE,
)


def age_hours(value: str) -> float | None:
    text = value.strip().casefold()
    if not text:
        return None
    if "just now" in text:
        return 0.0
    match = re.search(r"(\d+)\s+(minute|hour|day|week|month)s?\s+ago", text)
    if not match:
        return None
    amount = int(match.group(1))
    unit = match.group(2)
    factors = {"minute": 1 / 60, "hour": 1, "day": 24, "week": 168, "month": 720}
    return amount * factors[unit]


def load_summary(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        return json.loads(archive.read("capture_summary.json"))


def latest_ai_by_posting(con: sqlite3.Connection) -> dict[str, str]:
    rows = con.execute(
        """
        SELECT posting_id, decision, imported_at, reviewed_at, id
        FROM ai_reviews
        ORDER BY posting_id, imported_at DESC, reviewed_at DESC, id DESC
        """
    ).fetchall()
    result: dict[str, str] = {}
    for row in rows:
        result.setdefault(row["posting_id"], row["decision"])
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--db", default="backend/data/jolt.db")
    args = parser.parse_args()

    repo = Path.cwd()
    db = (repo / args.db).resolve()
    evidence_root = repo / ".jolt" / "discovery-batches" / args.batch_id

    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row

    searches = con.execute(
        """
        SELECT position, saved_search_id, label_snapshot, search_url_snapshot,
               capture_run_id, captured_count, verified_count, status, error
        FROM linkedin_discovery_batch_searches
        WHERE batch_id = ?
        ORDER BY position
        """,
        (args.batch_id,),
    ).fetchall()
    if not searches:
        raise SystemExit(f"No discovery searches found for batch {args.batch_id}")

    latest_ai = latest_ai_by_posting(con)
    per_search: list[dict[str, Any]] = []
    job_searches: dict[str, set[int]] = defaultdict(set)
    promoted_jobs: set[str] = set()
    organic_jobs: set[str] = set()

    for search in searches:
        zip_path = evidence_root / (
            f"{search['position']:02d}_{search['saved_search_id']}_capture.zip"
        )
        if zip_path.exists():
            summary = load_summary(zip_path)
            cards = summary.get("cards", []) or []
        else:
            summary = {}
            cards = []
        ids = {str(card.get("source_job_id", "")) for card in cards if card.get("source_job_id")}
        for job_id in ids:
            job_searches[job_id].add(search["position"])

        promoted = [card for card in cards if card.get("promoted") is True]
        for card in cards:
            job_id = str(card.get("source_job_id", "") or "")
            if not job_id:
                continue
            if card.get("promoted") is True:
                promoted_jobs.add(job_id)
            else:
                organic_jobs.add(job_id)

        ages = [
            hours
            for card in cards
            if (hours := age_hours(str(card.get("posted_age_text", "") or ""))) is not None
        ]

        if search["capture_run_id"]:
            capture_rows = con.execute(
                """
                SELECT ci.source_job_id, ci.posting_id, p.title, p.location, p.description
                FROM capture_items ci
                LEFT JOIN postings p ON p.id = ci.posting_id
                WHERE ci.capture_run_id = ?
                """,
                (search["capture_run_id"],),
            ).fetchall()
        else:
            capture_rows = []

        positive_signal = 0
        restrictive_signal = 0
        decisions = Counter()
        titles: set[str] = set()
        support_titles = 0
        admin_titles = 0

        for row in capture_rows:
            title = (row["title"] or "").strip()
            if title:
                titles.add(title.casefold())
                if "support" in title.casefold():
                    support_titles += 1
                if "administrator" in title.casefold() or "administrador" in title.casefold():
                    admin_titles += 1
            evidence = " ".join(
                str(value or "") for value in (row["location"], row["description"])
            )
            if POSITIVE_INTERNATIONAL.search(evidence):
                positive_signal += 1
            if RESTRICTIVE_INTERNATIONAL.search(evidence):
                restrictive_signal += 1
            posting_id = row["posting_id"]
            if posting_id and posting_id in latest_ai:
                decisions[latest_ai[posting_id]] += 1

        per_search.append(
            {
                "position": search["position"],
                "label": search["label_snapshot"],
                "url": search["search_url_snapshot"],
                "captured": len(cards),
                "verified": search["verified_count"],
                "status": search["status"],
                "error": search["error"],
                "evidence_present": zip_path.exists(),
                "job_ids": sorted(ids),
                "promoted_count": len(promoted),
                "promoted_pct": round(100 * len(promoted) / len(cards), 1) if cards else 0.0,
                "age_parsed_count": len(ages),
                "median_age_hours": round(statistics.median(ages), 2) if ages else None,
                "unique_titles": len(titles),
                "support_title_count": support_titles,
                "administrator_title_count": admin_titles,
                "international_positive_signal_count": positive_signal,
                "international_restrictive_signal_count": restrictive_signal,
                "ai_decisions": dict(decisions),
            }
        )

    for item in per_search:
        ids = set(item["job_ids"])
        item["exclusive_jobs"] = sum(len(job_searches[job_id]) == 1 for job_id in ids)
        item["shared_jobs"] = sum(len(job_searches[job_id]) > 1 for job_id in ids)

    pairs: list[dict[str, Any]] = []
    for i, left in enumerate(per_search):
        a = set(left["job_ids"])
        for right in per_search[i + 1 :]:
            b = set(right["job_ids"])
            union = a | b
            overlap = a & b
            pairs.append(
                {
                    "left_position": left["position"],
                    "right_position": right["position"],
                    "overlap": len(overlap),
                    "jaccard": round(len(overlap) / len(union), 3) if union else 0.0,
                }
            )

    report = {
        "batch_id": args.batch_id,
        "search_count": len(per_search),
        "unique_jobs": len(job_searches),
        "promoted_unique_jobs": len(promoted_jobs),
        "organic_unique_jobs": len(organic_jobs),
        "promoted_also_seen_organic": len(promoted_jobs & organic_jobs),
        "searches": per_search,
        "pair_overlap": sorted(pairs, key=lambda x: (-x["overlap"], -x["jaccard"])),
    }

    output = evidence_root / "search_experiment_analysis.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("=== JOLT LINKEDIN SEARCH EXPERIMENT ===")
    print("Batch:", args.batch_id)
    print("Searches:", len(per_search))
    print("Unique jobs:", len(job_searches))
    print("Unique promoted jobs:", len(promoted_jobs))
    print()

    for item in per_search:
        print(
            f"{item['position']:02d} | {item['label']} | status={item['status']}\n"
            f"     captured={item['captured']} promoted={item['promoted_count']} "
            f"({item['promoted_pct']}%) exclusive={item['exclusive_jobs']} "
            f"shared={item['shared_jobs']} unique_titles={item['unique_titles']} "
            f"median_age_h={item['median_age_hours']}\n"
            f"     intl_positive={item['international_positive_signal_count']} "
            f"intl_restrictive={item['international_restrictive_signal_count']} "
            f"AI={item['ai_decisions']}"
        )

    print()
    print("=== KEY A/B COMPARISONS ===")
    key_pairs = {(1, 2), (3, 4), (5, 6)}
    pair_index = {
        (p["left_position"], p["right_position"]): p
        for p in report["pair_overlap"]
    }
    for pair in sorted(key_pairs):
        p = pair_index.get(pair)
        if p:
            print(
                f"{pair[0]:02d}<->{pair[1]:02d}: overlap={p['overlap']} "
                f"jaccard={p['jaccard']}"
            )

    print()
    print("=== HIGHEST CROSS-SEARCH OVERLAP ===")
    for p in report["pair_overlap"][:10]:
        print(
            f"{p['left_position']:02d}<->{p['right_position']:02d}: "
            f"overlap={p['overlap']} jaccard={p['jaccard']}"
        )

    print()
    print("Report:", output)
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
