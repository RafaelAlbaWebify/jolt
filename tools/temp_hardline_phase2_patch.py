from pathlib import Path

p = Path("backend/src/jolt/database.py")
s = p.read_text(encoding="utf-8")
old = "    technical_fit: Mapped[int] = mapped_column(nullable=False)\n"
new = '''    technical_fit: Mapped[int | None] = mapped_column(nullable=True)
    hardline_status: Mapped[str] = mapped_column(String(20), default="PASS", nullable=False)
    hardline_reasons_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    location_eligibility: Mapped[str] = mapped_column(String(20), default="unknown", nullable=False)
    location_evidence_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    mandatory_requirements_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    mandatory_requirement_results_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    employment_constraints_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    fit_analysis_allowed: Mapped[bool] = mapped_column(default=True, nullable=False)
    decision_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
'''
if s.count(old) != 1:
    raise SystemExit(f"database technical_fit anchor count={s.count(old)}")
p.write_text(s.replace(old, new, 1), encoding="utf-8")

p = Path("backend/src/jolt/ai_review_pack.py")
s = p.read_text(encoding="utf-8")
s = s.replace(
    "from jolt.errors import JoltNotFoundError\n",
    "from jolt.errors import JoltNotFoundError\nfrom jolt.hardline_evidence import analyze_location_evidence\n",
    1,
)
s = s.replace('REVIEW_CONTRACT_VERSION = "1.0"', 'REVIEW_CONTRACT_VERSION = "1.1"', 1)
old = '''        source_raw_text = source.raw_text if source is not None else ""

        jobs_payload.append(
'''
new = '''        source_raw_text = source.raw_text if source is not None else ""
        location_signals = analyze_location_evidence(
            location=location,
            source_text=source_raw_text or description,
        )

        jobs_payload.append(
'''
if old not in s:
    raise SystemExit("ai_review_pack location anchor missing")
s = s.replace(old, new, 1)
old = '''                "location": location,
                "identity_status": posting.identity_status if posting is not None else "",
'''
new = '''                "location": location,
                "location_hardline_evidence": {
                    "location_eligibility": location_signals.location_eligibility,
                    "hardline_reject": location_signals.hardline_reject,
                    "positive_evidence": list(location_signals.positive_evidence),
                    "negative_evidence": list(location_signals.negative_evidence),
                },
                "identity_status": posting.identity_status if posting is not None else "",
'''
if old not in s:
    raise SystemExit("ai_review_pack payload location anchor missing")
s = s.replace(old, new, 1)
old = '''                "decision": "strong_pursue|pursue|conditional|reject",
                "priority_score": 0,
                "geography_status": "eligible|conditional|ineligible|unknown",
                "clearance_status": "clear|conditional|blocked|unknown",
                "language_status": "clear|conditional|blocked|unknown",
                "technical_fit": 0,
                "duplicate_of_posting_id": None,
                "summary": "",
                "reasons": [],
'''
new = '''                "hardline_status": "PASS|REJECT|MANUAL_REVIEW",
                "hardline_reasons": [],
                "location_eligibility": "eligible|conditional|ineligible|unknown",
                "location_evidence": [],
                "mandatory_requirements": [],
                "mandatory_requirement_results": [
                    {
                        "requirement": "",
                        "source_text": "",
                        "classification": "required|preferred|nice_to_have",
                        "candidate_evidence": "",
                        "result": "met|partial|unmet|unknown",
                        "hardline": False,
                    }
                ],
                "employment_constraints": [],
                "fit_analysis_allowed": True,
                "technical_fit_percent": None,
                "final_decision": "strong_pursue|pursue|conditional|reject",
                "decision_reason": "",
                "decision": "strong_pursue|pursue|conditional|reject",
                "priority_score": 0,
                "geography_status": "eligible|conditional|ineligible|unknown",
                "clearance_status": "clear|conditional|blocked|unknown",
                "language_status": "clear|conditional|blocked|unknown",
                "technical_fit": None,
                "duplicate_of_posting_id": None,
                "summary": "",
                "reasons": [],
'''
if old not in s:
    raise SystemExit("response template anchor missing")
p.write_text(s.replace(old, new, 1), encoding="utf-8")

p = Path("backend/tests/test_ai_review_pack.py")
s = p.read_text(encoding="utf-8")
old = '        assert document["review_contract_version"] == "1.0"\n'
new = '''        assert document["review_contract_version"] == "1.1"
        assert document["jobs"][0]["location_hardline_evidence"]["location_eligibility"] in {"eligible", "conditional", "ineligible"}
        assert document["response_template"]["jobs"][0]["hardline_status"] == "PASS|REJECT|MANUAL_REVIEW"
        assert document["response_template"]["jobs"][0]["technical_fit_percent"] is None
'''
if old not in s:
    raise SystemExit("test review version anchor missing")
p.write_text(s.replace(old, new, 1), encoding="utf-8")
