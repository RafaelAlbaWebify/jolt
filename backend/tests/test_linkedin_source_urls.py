from jolt.linkedin_source_urls import absolute_linkedin_url, normalize_linkedin_search_url


def test_normalizes_relative_linkedin_job_url() -> None:
    assert (
        absolute_linkedin_url("/jobs/view/4443227805/?trackingId=abc")
        == "https://www.linkedin.com/jobs/view/4443227805/?trackingId=abc"
    )


def test_normalizes_protocol_relative_linkedin_job_url() -> None:
    assert (
        absolute_linkedin_url("//www.linkedin.com/jobs/view/4443227805/")
        == "https://www.linkedin.com/jobs/view/4443227805/"
    )


def test_preserves_absolute_job_url() -> None:
    url = "https://www.linkedin.com/jobs/view/4443227805/"
    assert absolute_linkedin_url(url) == url


def test_preserves_empty_url() -> None:
    assert absolute_linkedin_url("") == ""


def test_search_pagination_urls_share_one_canonical_identity() -> None:
    page_one = (
        "https://www.linkedin.com/jobs/search/?currentJobId=4469309319"
        "&f_TPR=r604800&f_WT=2&geoId=91000000&keywords=IT%20Support"
        "&origin=JOB_SEARCH_PAGE_JOB_FILTER&refresh=true&sortBy=DD"
    )
    page_two = (
        "https://www.linkedin.com/jobs/search/?currentJobId=4469440645"
        "&f_TPR=r604800&f_WT=2&geoId=91000000&keywords=IT%20Support"
        "&origin=JOB_SEARCH_PAGE_JOB_FILTER&refresh=true&sortBy=DD&start=25"
    )
    page_three = (
        "https://www.linkedin.com/jobs/search/?currentJobId=4441622734"
        "&f_TPR=r604800&f_WT=2&geoId=91000000&keywords=IT%20Support"
        "&origin=JOB_SEARCH_PAGE_JOB_FILTER&refresh=true&sortBy=DD&start=50"
    )

    expected = (
        "https://www.linkedin.com/jobs/search/?f_TPR=r604800&f_WT=2"
        "&geoId=91000000&keywords=IT+Support&sortBy=DD"
    )
    assert normalize_linkedin_search_url(page_one) == expected
    assert normalize_linkedin_search_url(page_two) == expected
    assert normalize_linkedin_search_url(page_three) == expected


def test_different_search_keywords_keep_distinct_canonical_urls() -> None:
    it_support = (
        "https://www.linkedin.com/jobs/search/?f_TPR=r604800&f_WT=2"
        "&geoId=91000000&keywords=IT%20Support&sortBy=DD"
    )
    application_support = (
        "https://www.linkedin.com/jobs/search/?currentJobId=4468998338"
        "&f_TPR=r604800&f_WT=2&geoId=91000000"
        "&keywords=Application%20Support%20Engineer"
        "&origin=JOB_SEARCH_PAGE_SEARCH_BUTTON&refresh=true&sortBy=DD"
    )

    assert normalize_linkedin_search_url(it_support) != normalize_linkedin_search_url(
        application_support
    )
