from jolt.professional_intelligence_bounded_capture import _looks_like_linkedin_authwall


def test_detects_linkedin_authwall_url_and_signup_page() -> None:
    assert _looks_like_linkedin_authwall(
        "https://www.linkedin.com/authwall?sessionRedirect=https%3A%2F%2Fwww.linkedin.com%2Fin%2Frafael-alba-tech",
        "Sign Up | LinkedIn",
        "LinkedIn respects your privacy\nJoin LinkedIn\nAgree & Join\nAlready on Linkedin? Sign in",
    )


def test_does_not_flag_authenticated_profile_content() -> None:
    assert not _looks_like_linkedin_authwall(
        "https://www.linkedin.com/in/rafael-alba-tech/",
        "Rafael Alba | LinkedIn",
        "Rafael Alba Local IT Engineer Application Support Cloud Operations Professional Experience Skills Activity",
    )
