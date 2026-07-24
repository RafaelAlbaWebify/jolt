from jolt.professional_intelligence_sources import list_professional_intelligence_sources


def test_confirmed_professional_intelligence_registry_is_exact_and_safe() -> None:
    sources = list_professional_intelligence_sources()

    assert len(sources) == 14
    assert len({source.source_id for source in sources}) == 14
    assert len({source.url for source in sources}) == 14
    assert all(source.url.startswith("https://www.linkedin.com/") for source in sources)
    assert all(source.capture_mode == "supervised_read_only" for source in sources)
    assert all(source.enabled for source in sources)

    initial_scope = [source for source in sources if source.initial_scope]
    assert [source.label for source in initial_scope] == [
        "Main profile",
        "Experience",
        "Featured",
        "All activity",
        "Certifications",
        "Skills",
        "Jobs based on preferences",
        "Jobs that match the profile",
    ]

    deferred_labels = {source.label for source in sources if not source.initial_scope}
    assert deferred_labels == {
        "Connections",
        "Groups",
        "Pages",
        "Newsletters",
        "Notifications",
        "Feed",
    }


def test_registry_results_are_defensive_copies() -> None:
    first = list_professional_intelligence_sources()
    first[0].label = "Changed by caller"

    second = list_professional_intelligence_sources()
    assert second[0].label == "Main profile"
