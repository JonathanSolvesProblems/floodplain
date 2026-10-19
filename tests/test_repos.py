from floodplain.repos import github_repo, tag_candidates


def test_github_repo_prefers_source_over_homepage():
    urls = {
        "Homepage": "https://example.com",
        "Source": "https://github.com/simonw/llm",
        "Issues": "https://github.com/simonw/llm/issues",
    }
    assert github_repo(urls) == ("simonw", "llm")


def test_github_repo_strips_git_suffix_and_subpaths():
    assert github_repo({"Repository": "https://github.com/langroid/langroid.git"}) == ("langroid", "langroid")
    assert github_repo({"Homepage": "https://github.com/a/b/tree/main/pkg"}) == ("a", "b")


def test_github_repo_none_when_absent():
    assert github_repo({"Homepage": "https://gitlab.com/x/y"}) is None


def test_fuzzy_tag_matches_monorepo_prefixes():
    from floodplain.repos import fuzzy_tag
    tags = {
        "python-openinference-instrumentation-openai-v0.1.54": "a",
        "python-openinference-instrumentation-openai-v0.1.53": "b",
        "python-openinference-instrumentation-v0.1.54": "c",
        "js-openinference-instrumentation-openai-v0.1.54": "d",
    }
    # Two tags contain the name and end with the version (python- and js-), so ambiguous -> None
    assert fuzzy_tag("openinference-instrumentation-openai", "0.1.54", tags) is None
    del tags["js-openinference-instrumentation-openai-v0.1.54"]
    assert fuzzy_tag("openinference-instrumentation-openai", "0.1.54", tags) == \
        "python-openinference-instrumentation-openai-v0.1.54"
    assert fuzzy_tag("livekit-plugins-openai", "1.6.9", {"livekit-plugins-openai@1.6.9": "x"}) == \
        "livekit-plugins-openai@1.6.9"


def test_tag_candidates_cover_common_schemes():
    c = tag_candidates("langchain-openai", "0.3.1")
    for expected in ("v0.3.1", "0.3.1", "langchain-openai-0.3.1", "langchain-openai==0.3.1", "openai==0.3.1"):
        assert expected in c
