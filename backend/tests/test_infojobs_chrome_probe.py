from __future__ import annotations

from unittest.mock import Mock

import pytest

from jolt.infojobs_chrome_probe import probe_page


def test_infojobs_probe_rejects_external_pages() -> None:
    page = Mock(url="https://example.com/jobs")
    with pytest.raises(ValueError, match="infojobs.net"):
        probe_page(page)
    page.evaluate.assert_not_called()


def test_infojobs_probe_uses_browser_side_read_only_inspection() -> None:
    page = Mock(url="https://www.infojobs.net/jobsearch/search-results/list.xhtml")
    page.evaluate.return_value = {"candidateCount": 2, "offerCandidates": []}
    result = probe_page(page)
    assert result["candidateCount"] == 2
    page.evaluate.assert_called_once()
    script = page.evaluate.call_args.args[0]
    assert "querySelectorAll" in script
    assert ".click(" not in script
    assert ".submit(" not in script
