from __future__ import annotations

import re
from pathlib import Path

from jolt.errors import JoltNotFoundError


def test_jolt_not_found_is_specific_but_lookup_compatible() -> None:
    assert issubclass(JoltNotFoundError, LookupError)
    assert not isinstance(KeyError("internal defect"), JoltNotFoundError)
    assert not isinstance(IndexError("internal defect"), JoltNotFoundError)


def test_production_code_has_no_generic_lookup_error_boundary() -> None:
    source_root = Path(__file__).parents[1] / "src" / "jolt"
    violations: list[str] = []

    for path in sorted(source_root.rglob("*.py")):
        text = path.read_text(encoding="utf-8")

        if re.search(r"\braise\s+LookupError\b", text):
            violations.append(f"{path.name}: raise LookupError")

        if re.search(r"\bexcept\s+LookupError\b", text):
            violations.append(f"{path.name}: except LookupError")

    assert violations == []


def test_internal_lookup_subclasses_are_not_jolt_not_found() -> None:
    internal_errors = [
        KeyError("missing dictionary key"),
        IndexError("missing list position"),
    ]

    assert all(not isinstance(error, JoltNotFoundError) for error in internal_errors)
