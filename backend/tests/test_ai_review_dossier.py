from jolt.ai_review_dossier import enrich_review_inbox_with_dossiers


def _ledger():
    return {
        "source_evidence": [
            {
                "title": "Experience",
                "evidence_ref": "linkedin_capture:experience",
                "visible_text": "IT Support Engineer: Windows support and DNS troubleshooting.",
            },
            {
                "title": "Licenses & certifications",
                "evidence_ref": "linkedin_capture:certification",
                "visible_text": "AWS Cloud Solutions Architect course.",
            },
        ]
    }


def _job(posting_id, description, requirements):
    return {
        "posting_id": posting_id,
        "location": "Vigo",
        "analysis_text": description,
        "preanalysis": {
            "requirement_candidates": [
                {
                    "source_text": text,
                    "classification_candidate": "required",
                }
                for text in requirements
            ],
            "uncertainties": [],
        },
    }


def test_crosswalk_provenance_never_asserts_experience_or_fit():
    jobs = [_job("a", "Remote technical support in Spain", ["Required Windows and AWS"])]
    result = enrich_review_inbox_with_dossiers({"jobs": jobs}, _ledger())
    assert result is not None
    dossier = result["jobs"][0]["evaluation_dossier"]
    crosswalk = dossier["requirement_skill_crosswalk"][0]
    assert crosswalk["candidate_mentions"]["windows"][0]["source_section"] == "experience"
    assert crosswalk["candidate_mentions"]["aws"][0]["source_section"] == (
        "licenses & certifications"
    )
    assert crosswalk["candidate_mentions"]["aws"][0]["claim_status"] == "unverified_mention"
    assert dossier["final_decision"] is None


def test_remote_onsite_conflict_requires_verification():
    jobs = [_job("b", "Fully remote. Three days per week on-site in Valladolid.", [])]
    result = enrich_review_inbox_with_dossiers({"jobs": jobs}, _ledger())
    assert result is not None
    dossier = result["jobs"][0]["evaluation_dossier"]
    assert "remote_and_office_presence_language" in dossier["work_model_warnings"]
    assert dossier["priority_for_ai"] == "high"


def test_keeps_all_342_jobs_and_existing_fields_unchanged():
    jobs = [_job(str(i), "Technical support", ["SQL required"]) for i in range(342)]
    inbox = {"jobs": jobs, "response_template": {"contract_type": "unchanged"}}
    result = enrich_review_inbox_with_dossiers(inbox, _ledger())
    assert result is not None
    assert result["dossier_metadata"]["jobs_enriched"] == 342
    assert len(result["jobs"]) == 342
    assert result["response_template"] == {"contract_type": "unchanged"}
    assert all(job["preanalysis"]["requirement_candidates"] for job in result["jobs"])


def test_no_inbox_is_safe_and_no_candidate_evidence_is_not_a_mismatch():
    assert enrich_review_inbox_with_dossiers(None, _ledger()) is None
    result = enrich_review_inbox_with_dossiers(
        {"jobs": [_job("x", "Support", ["Required SQL"])], "metadata": "original"},
        {"source_evidence": []},
    )
    assert result is not None
    crosswalk = result["jobs"][0]["evaluation_dossier"]["requirement_skill_crosswalk"]
    assert crosswalk[0]["candidate_mentions"]["sql"] == []
    assert result["metadata"] == "original"


def test_evidence_contains_exact_excerpt_not_only_section_ref():
    inbox = {"jobs": [_job("one", "Support", ["Windows required"])]}
    result = enrich_review_inbox_with_dossiers(inbox, _ledger())
    assert result is not None
    mention = result["jobs"][0]["evaluation_dossier"]["requirement_skill_crosswalk"][0][
        "candidate_mentions"
    ]["windows"][0]
    assert "Windows support" in mention["source_text"]
    assert mention["claim_status"] == "unverified_mention"


def test_windows_forms_does_not_match_windows_support():
    inbox = {"jobs": [_job("forms", "Windows Forms developer", ["Windows Forms required"])]}
    result = enrich_review_inbox_with_dossiers(inbox, _ledger())
    assert result is not None
    assert result["jobs"][0]["evaluation_dossier"]["requirement_skill_crosswalk"] == []


def test_explicit_hybrid_is_not_labelled_remote_onsite_contradiction():
    inbox = {"jobs": [_job("hybrid", "Hybrid remote and on-site schedule", [])]}
    result = enrich_review_inbox_with_dossiers(inbox, _ledger())
    assert result is not None
    warnings = result["jobs"][0]["evaluation_dossier"]["work_model_warnings"]
    assert "remote_and_office_presence_language" not in warnings


def test_linkedin_chrome_not_counted_as_certification_or_experience():
    ledger = {
        "source_evidence": [
            {
                "title": "Licenses & certifications",
                "evidence_ref": "certs",
                "visible_text": (
                    "Application Support Engineer | M365, Entra ID, Windows\\n"
                    "Licenses & certifications\\n"
                    "AWS Cloud Solutions Architect\\n"
                    "Amazon Web Services (AWS)\\n"
                    "Issued May 2024\\n"
                    "Who your viewers also viewed\\n"
                    "Windows Administrator\\n"
                ).replace("\\\\n", "\\n"),
            },
            {
                "title": "Experience",
                "evidence_ref": "work",
                "visible_text": (
                    "Application Support Engineer | M365, Entra ID, Windows\\n"
                    "Experience\\n"
                    "IT Support Engineer\\n"
                    "Quental · Contract\\n"
                    "Investigated Windows and DNS incidents\\n"
                    "Profile language\\n"
                    "AWS supporter\\n"
                ).replace("\\\\n", "\\n"),
            },
        ]
    }
    inbox = {"jobs": [_job("one", "IT support", ["Required AWS, Windows and Entra ID"])]}
    result = enrich_review_inbox_with_dossiers(inbox, ledger)
    assert result is not None
    mentions = result["jobs"][0]["evaluation_dossier"]["requirement_skill_crosswalk"][0][
        "candidate_mentions"
    ]
    assert mentions["entra id"] == []
    assert mentions["aws"][0]["source_section"] == "licenses & certifications"
    assert mentions["aws"][0]["source_context"] == "AWS Cloud Solutions Architect"
    assert mentions["windows"][0]["source_section"] == "experience"
    assert mentions["windows"][0]["source_context"] == "Quental"


def test_uncertain_unanchored_profile_capture_never_provides_skill_evidence():
    ledger = {"source_evidence": [
        {"title": "Experience", "evidence_ref": "broken",
         "visible_text": "Application Support Engineer | Windows, Azure"}
    ]}
    result = enrich_review_inbox_with_dossiers(
        {"jobs": [_job("one", "Support", ["Windows required"])]}, ledger
    )
    assert result is not None
    mentions = result["jobs"][0]["evaluation_dossier"]["requirement_skill_crosswalk"][0][
        "candidate_mentions"
    ]
    assert mentions["windows"] == []
