import json

from jolt.market_strategy_package import build_market_strategy_package_json
from jolt.unified_ai_work_package import UnifiedAIWorkPackage


def test_market_export_is_compact_and_review_free(monkeypatch) -> None:
    import jolt.market_strategy_package as market_package

    monkeypatch.setattr(market_package, "build_global_context_snapshot", lambda: {})
    monkeypatch.setattr(market_package, "global_context_version", lambda context: "test-context")

    def local_aggregates(session):
        return {
            "total_unique_roles": 3,
            "target_role_count": 2,
            "evaluation_coverage": {"evaluated_count": 2, "missing_count": 1},
            "evidence_provenance": {"canonical_role_count": 3},
            "target": {
                "total_roles": 2,
                "top_skills": [{"label": "SQL", "count": 2}],
                "raw_description": "SHOULD_NOT_EXPORT",
            },
            "all": {
                "total_roles": 3,
                "top_skills": [{"label": "SQL", "count": 2}],
            },
            "duplicate_groups": [{"description": "SHOULD_NOT_EXPORT"}],
        }

    monkeypatch.setattr(market_package, "build_market_intelligence", local_aggregates)
    encoded = build_market_strategy_package_json(None)
    decoded = json.loads(encoded)
    assert "SHOULD_NOT_EXPORT" not in encoded.decode()
    package = UnifiedAIWorkPackage.model_validate(decoded)
    assert package.review_inbox is None
    assert package.candidate_evidence == {}
    assert len(package.exchanges) == 1
    assert package.exchanges[0].scope.section == "market_insights"
    assert package.exchanges[0].evidence["total_unique_roles"] == 3
