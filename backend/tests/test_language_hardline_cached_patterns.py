from jolt.language_hardline import _alias_pattern, _language_mentions


def test_language_alias_pattern_is_cached() -> None:
    first = _alias_pattern("english")
    assert first is _alias_pattern("english")
    assert first.search("English required")
    assert not first.search("nonenglish")


def test_cached_language_patterns_preserve_mention_order() -> None:
    text = "English and French required; German preferred"
    first = _language_mentions(text)
    second = _language_mentions(text)
    assert first == second
    assert any(item[0] == "english" for item in first)
