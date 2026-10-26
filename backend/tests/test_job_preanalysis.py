from types import SimpleNamespace

from jolt.job_preanalysis import build_job_preanalysis


def analyze(description: str, geography: str = "conditional"):
    return build_job_preanalysis(
        title="Support",
        description=description,
        location="Spain",
        location_evidence=SimpleNamespace(
            location_eligibility=geography,
            hardline_reject=False,
            positive_evidence=(),
            negative_evidence=(),
        ),
        language_evidence=SimpleNamespace(as_dict=lambda: {"document_language": "english"}),
    )


def test_required_vs_preferred_and_no_fabricated_match():
    evidence = analyze("Must have SQL experience.\nNice to have Azure exposure.")
    requirements = evidence["requirement_candidates"]
    assert len(requirements) == 2
    assert requirements[0]["classification_candidate"] == "required"
    assert requirements[1]["classification_candidate"] == "preferred"
    assert all(r["candidate_match"] == "unknown" for r in requirements)
    assert evidence["final_decision"] is None


def test_commercial_signal_does_not_auto_reject():
    evidence = analyze("Venta puerta a puerta para nuevos clientes.")
    assert evidence["commercial_exclusion_signals"]
    assert evidence["final_decision"] is None


def test_missing_evidence_is_explicit_and_deterministic():
    evidence = analyze("", "unknown")
    assert evidence["requirement_candidates"] == []
    assert len(evidence["uncertainties"]) >= 2
    assert analyze("Required SQL experience.") == analyze("Required SQL experience.")


def test_unified_work_package_compaction_preserves_preanalysis():
    from jolt.unified_ai_work_package import _compact_review_inbox_payload

    original = analyze("Must have SQL experience.")
    bundle = {
        "jobs": [
            {
                "posting_id": "p-001",
                "analysis_text": "Must have SQL experience.",
                "description_clean": "Must have SQL experience.",
                "source_text_clean": "Must have SQL experience.",
                "preanalysis": original,
                "audit": {
                    "source_raw_text": "Must have SQL experience.",
                    "source_raw_text_sha256": original["input_sha256"],
                },
            }
        ]
    }
    compacted = _compact_review_inbox_payload(bundle)
    job = compacted["jobs"][0]
    assert job["preanalysis"] == original
    assert job["analysis_text"] == "Must have SQL experience."
    assert "description_clean" not in job
    assert "source_text_clean" not in job
    assert "source_raw_text" not in job["audit"]
    assert compacted["evidence_compaction"]["current_jobs_omitted"] == 0


def test_requirement_sections_and_boundary_do_not_include_duties():
    evidence = analyze(
        "Requirements:\n"
        "SQL and Windows administration\n"
        "At least 2 years in technical support\n"
        "Responsibilities:\n"
        "Manage ticket queue\n"
        "Benefits:\n"
        "Flexible holidays"
    )
    extracted = [item["source_text"] for item in evidence["requirement_candidates"]]
    assert "SQL and Windows administration" in extracted
    assert "At least 2 years in technical support" in extracted
    assert "Manage ticket queue" not in extracted
    assert "Flexible holidays" not in extracted


def test_spanish_section_and_preferred_section():
    evidence = analyze(
        "Requisitos:\n"
        "Experiencia gestionando incidencias IT\n"
        "Se valorará:\n"
        "Conocimiento de Azure\n"
        "Funciones:\n"
        "Prestar soporte a usuarios"
    )
    extracted = evidence["requirement_candidates"]
    assert extracted[0]["classification_candidate"] == "required"
    assert extracted[1]["classification_candidate"] == "preferred"
    assert all("Prestar soporte" not in item["source_text"] for item in extracted)


def test_no_autorejection_on_remote_or_other_language():
    evidence = analyze("Required German language. Remote within Germany.", "conditional")
    assert evidence["final_decision"] is None
    assert evidence["authority"] == "advisory_only"
    assert evidence["review_required"] is True
