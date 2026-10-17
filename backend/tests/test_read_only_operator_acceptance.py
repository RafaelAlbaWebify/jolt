"""Acceptance must reject stale runtime evidence instead of giving false PASS."""

import pytest

from jolt.read_only_operator_acceptance import verify_loaded_commit


def test_exact_loaded_commit_passes():
    identity = {"loaded_git": {"commit_sha": "abc123"}}
    assert verify_loaded_commit(identity, "abc123") == "abc123"


@pytest.mark.parametrize(
    "identity",
    [
        {},
        {"loaded_git": {}},
        {"loaded_git": {"commit_sha": None}},
        {"loaded_git": {"commit_sha": "old"}},
        None,
    ],
)
def test_missing_or_stale_loaded_commit_fails(identity):
    with pytest.raises(RuntimeError):
        verify_loaded_commit(identity, "new")
