"""JOLT backend package."""

from jolt.url_identity import canonicalize_source_url


def _install_url_identity_boundary() -> None:
    # Import after the package exists, then replace the workflow's canonicalizer.
    # SourceDocument.source_url remains untouched; only Posting.canonical_url changes.
    from jolt import workflow

    workflow.normalize_url = canonicalize_source_url


_install_url_identity_boundary()
