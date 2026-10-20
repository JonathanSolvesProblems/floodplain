"""Find the upstream's own migration guidance for a break, at runtime, with Tavily.

When triage names a symbol (httpx, certifi, a removed attribute), the fixer
needs the upstream's migration notes for that symbol, which live outside the
release notes: a docs page, a linked markdown file, a pinned issue. Tavily
search fetches them. Everything returned is recorded with its URL so the
writeup can say where each fix's guidance came from.

Two guards keep the fixer from copying the answer. The search is limited to
pages dated no later than end_date (the day after the release, which is the
window this tool is meant to act in), and any page from the dependent's own
repository, or naming it, is dropped and recorded as excluded. Without them,
the top hit for openai 3.0.0 is llm's own issue, where the maintainer's fix is
discussed, and a matching patch would prove nothing.

Every Tavily response is written to a cache directory that is committed with
the results, keyed by the query. A later run reads the cache first, so
reproducing a result needs no Tavily key and spends no credits, and it sees
exactly the pages the original run saw. Order of preference: cache, live
Tavily, the local fallback file, nothing. The record says which was used.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Guidance:
    query: str
    source: str                      # "tavily" | "tavily-cache" | "local-fallback" | "none", plus a note
    urls: list[str] = field(default_factory=list)
    text: str = ""
    fetched_at: str | None = None    # when Tavily returned these pages
    excluded: list[str] = field(default_factory=list)  # dropped for naming the dependent
    end_date: str | None = None


def cache_key(query: str, exclude_repos: list[str], end_date: str | None) -> str:
    return f"{query}|exclude={','.join(sorted({r.lower() for r in exclude_repos}))}|end={end_date or ''}"


def cache_path(cache_dir: Path, key: str) -> Path:
    return cache_dir / f"{hashlib.sha1(key.encode()).hexdigest()[:12]}.json"


def read_cache(cache_dir: Path | None, key: str) -> dict | None:
    if not cache_dir:
        return None
    p = cache_path(cache_dir, key)
    if not p.exists():
        return None
    rec = json.loads(p.read_text(encoding="utf-8"))
    return rec if rec.get("key") == key and rec.get("text") else None


def names_dependent(result: dict, exclude_repos: list[str]) -> bool:
    hay = " ".join(str(result.get(k) or "") for k in ("url", "title", "content", "raw_content")).lower()
    return any(slug.lower() in hay for slug in exclude_repos if slug)


def build_text(results: list[dict], max_chars: int) -> str:
    chunks = []
    for r in results:
        body = r.get("raw_content") or r.get("content") or ""
        if body and r.get("url"):
            chunks.append(f"--- {r['url']}\n{body[: max_chars // max(1, len(results))]}")
    return "\n\n".join(chunks)[:max_chars]


def from_cache(rec: dict, source: str) -> Guidance:
    return Guidance(query=rec["query"], source=source, urls=rec["urls"], text=rec["text"],
                    fetched_at=rec.get("fetched_at"), excluded=rec.get("excluded", []),
                    end_date=rec.get("end_date"))


async def find_guidance(target: str, release: str, symbol: str | None, category: str,
                        fallback: Path | None = None, cache_dir: Path | None = None,
                        refresh: bool = False, exclude_repos: list[str] | None = None,
                        end_date: str | None = None, min_score: float = 0.6,
                        max_pages: int = 3, max_chars: int = 12000) -> Guidance:
    q = f"{target} python package {release} migration guide {symbol or category} breaking change"
    exclude_repos = exclude_repos or []
    key = cache_key(q, exclude_repos, end_date)
    cached = None if refresh else read_cache(cache_dir, key)
    if cached:
        return from_cache(cached, "tavily-cache")

    note = ""
    api_key = os.environ.get("TAVILY_API_KEY")
    if api_key:
        try:
            from tavily import AsyncTavilyClient
            client = AsyncTavilyClient(api_key=api_key)
            opts = {"end_date": end_date} if end_date else {}
            res = await client.search(query=q, search_depth="advanced", max_results=8,
                                      chunks_per_source=3, **opts)
            results = res.get("results", [])
            kept = [r for r in results if (r.get("score") or 0) >= min_score][:max_pages]
            if kept:
                # Search returns short chunks; extract fetches each relevant page in full.
                ext = await client.extract(urls=[r["url"] for r in kept], format="markdown")
                full = {e["url"]: e.get("raw_content") or "" for e in ext.get("results", [])}
                for r in kept:
                    r["raw_content"] = full.get(r["url"], "")
            # Checked after extraction too: a full page can name the dependent when its snippet did not.
            excluded = [r.get("url", "") for r in kept if names_dependent(r, exclude_repos)]
            kept = [r for r in kept if not names_dependent(r, exclude_repos)]
            text = build_text(kept, max_chars)
            if text:
                g = Guidance(query=q, source="tavily", urls=[r["url"] for r in kept if r.get("url")],
                             text=text, fetched_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                             excluded=excluded, end_date=end_date)
                if cache_dir:
                    cache_dir.mkdir(parents=True, exist_ok=True)
                    cache_path(cache_dir, key).write_text(json.dumps(
                        {"key": key, "query": q, "end_date": end_date, "exclude_repos": exclude_repos, "min_score": min_score,
                         "fetched_at": g.fetched_at, "urls": g.urls, "excluded": excluded, "text": g.text,
                         "results": [{k: r.get(k) for k in ("url", "title", "score", "published_date")}
                                     for r in kept]},
                        indent=2), encoding="utf-8")
                return g
            note = " (tavily returned no usable pages)"
        except Exception as e:  # noqa: BLE001 - quota or network: fall through, but say why
            note = f" (tavily error: {type(e).__name__}: {e})"
        # A stale cache entry beats the local file when a refresh was asked for but failed.
        stale = read_cache(cache_dir, key) if refresh else None
        if stale:
            return from_cache(stale, "tavily-cache" + note)
    if fallback and fallback.exists():
        return Guidance(query=q, source="local-fallback" + note, urls=[str(fallback)],
                        text=fallback.read_text(encoding="utf-8")[:max_chars])
    return Guidance(query=q, source="none" + note)


if __name__ == "__main__":
    import sys
    g = asyncio.run(find_guidance("openai", "3.0.0", "httpx", "undeclared-transitive-dependency",
                                  fallback=Path("data/openai-3.0.0/migration_guide.md"),
                                  cache_dir=Path("data/openai-3.0.0/research"),
                                  exclude_repos=["simonw/llm"], end_date="2026-08-20"))
    print(g.source, g.fetched_at, "excluded:", g.excluded, file=sys.stderr)
    for f in Path("data/openai-3.0.0/research").glob("*.json"):
        for r in json.loads(f.read_text(encoding="utf-8"))["results"]:
            print(f"  {r['score'] or 0:.2f} {r.get('published_date') or '-':<32} {r['url']}", file=sys.stderr)
    print(g.text[:1500])
