from __future__ import annotations

import inspect

from jolt import review_audit


def test_review_audit_waits_for_rendered_opportunity_data() -> None:
    source = inspect.getsource(review_audit.audit)

    assert 'wait_until="domcontentloaded"' in source
    assert "expectedCount" in source
    assert "expectedTitle" in source
    assert "networkidle" not in source
