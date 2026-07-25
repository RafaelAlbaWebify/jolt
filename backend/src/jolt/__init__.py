"""JOLT backend package."""

from jolt.url_identity import canonicalize_source_url


def _install_url_identity_boundary() -> None:
    # Import after the package exists, then replace only the URL canonicalization boundary.
    from jolt import workflow

    # SourceDocument.source_url remains untouched; only Posting.canonical_url changes.
    workflow.normalize_url = canonicalize_source_url


_install_url_identity_boundary()
