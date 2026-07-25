"""JOLT backend package."""

from jolt.reversible_application_workflow import transition_application_reversibly
from jolt.url_identity import canonicalize_source_url


def _install_workflow_boundaries() -> None:
    # Import after the package exists, then replace workflow boundaries used by the API.
    from jolt import workflow

    # SourceDocument.source_url remains untouched; only Posting.canonical_url changes.
    workflow.normalize_url = canonicalize_source_url
    workflow.transition_application = transition_application_reversibly


_install_workflow_boundaries()
