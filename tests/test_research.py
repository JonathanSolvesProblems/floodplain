import asyncio
import json
import sys
import types

from floodplain.research import cache_path, find_guidance


def fake_tavily(monkeypatch, results=None, error=None):
    calls = []

    class Client:
        def __init__(self, api_key):
            pass

        async def search(self, **kw):
            calls.append(kw)
            if error:
                raise error
            return {"results": [{"url": r["url"], "content": "snippet", "score": r.get("score", 0.9)}
                                for r in results or []]}

        async def extract(self, urls, **kw):
            return {"results": [{"url": r["url"], "raw_content": r["raw_content"]}
                                for r in results or [] if r["url"] in urls]}

    monkeypatch.setitem(sys.modules, "tavily", types.SimpleNamespace(AsyncTavilyClient=Client))
    monkeypatch.setenv("TAVILY_API_KEY", "test")
    return calls


def run(**kw):
    return asyncio.run(find_guidance("openai", "3.0.0", "httpx", "cat", **kw))


def test_live_result_is_cached_and_replayed_without_a_key(tmp_path, monkeypatch):
    calls = fake_tavily(monkeypatch, [{"url": "https://x/guide", "raw_content": "use httpx2"}])
    g = run(cache_dir=tmp_path)
    assert g.source == "tavily" and "use httpx2" in g.text and g.fetched_at
    monkeypatch.delenv("TAVILY_API_KEY")
    again = run(cache_dir=tmp_path)
    assert again.source == "tavily-cache" and again.text == g.text and again.urls == ["https://x/guide"]
    assert len(calls) == 1


def test_quota_error_on_refresh_falls_back_to_the_stale_cache(tmp_path, monkeypatch):
    fake_tavily(monkeypatch, [{"url": "https://x/guide", "raw_content": "old pages"}])
    run(cache_dir=tmp_path)
    fake_tavily(monkeypatch, error=RuntimeError("usage limit exceeded"))
    g = run(cache_dir=tmp_path, refresh=True)
    assert g.source.startswith("tavily-cache (tavily error") and "old pages" in g.text


def test_no_key_and_no_cache_uses_the_local_file_and_says_so(tmp_path, monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    local = tmp_path / "guide.md"
    local.write_text("local guide", encoding="utf-8")
    g = run(cache_dir=tmp_path / "cache", fallback=local)
    assert g.source == "local-fallback" and g.text == "local guide"


def test_a_cache_file_for_a_different_query_is_ignored(tmp_path, monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    q = "openai python package 3.0.0 migration guide httpx breaking change|exclude=|end="
    cache_path(tmp_path, q).write_text(json.dumps({"key": "something else", "text": "x", "urls": []}))
    assert run(cache_dir=tmp_path).source == "none"


def test_pages_naming_the_dependent_are_dropped_even_when_only_the_full_text_does(tmp_path, monkeypatch):
    fake_tavily(monkeypatch, [
        {"url": "https://x/guide", "raw_content": "httpx2 migration notes"},
        {"url": "https://x/thread", "raw_content": "simonw/llm fixed it by pinning openai<3"},
        {"url": "https://x/weak", "raw_content": "unrelated", "score": 0.2},
    ])
    g = run(cache_dir=tmp_path, exclude_repos=["simonw/llm"])
    assert g.urls == ["https://x/guide"] and g.excluded == ["https://x/thread"]
    assert "pinning" not in g.text and "unrelated" not in g.text
