import os


# Tests must never change behavior because a developer has a private JOLT profile
# installed in the repository's ignored .jolt directory. Individual tests that
# exercise private-profile loading can override this environment variable.
os.environ["JOLT_PROFILE_PATH"] = "__jolt_test_profile_does_not_exist__.json"
