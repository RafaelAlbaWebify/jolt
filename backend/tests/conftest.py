from __future__ import annotations

import os
from pathlib import Path


# Tests must never change behavior because a developer has a private JOLT profile
# installed in the repository's ignored .jolt directory. Individual tests that
# exercise private-profile loading can override this environment variable.
_TEST_PROFILE_PATH = Path(__file__).resolve().parent / "fixtures" / "nonexistent.private.json"
os.environ["JOLT_PROFILE_PATH"] = str(_TEST_PROFILE_PATH)
