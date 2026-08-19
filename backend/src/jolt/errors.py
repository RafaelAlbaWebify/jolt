from __future__ import annotations


class JoltNotFoundError(LookupError):
    """Raised only when a requested JOLT resource genuinely does not exist."""
