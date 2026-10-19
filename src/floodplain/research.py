"""Find the upstream's own migration guidance for a break, at runtime, with Tavily.

When triage names a symbol (httpx, certifi, a removed attribute), the fixer
needs the upstream's migration notes for that symbol, which live outside the
release notes: a docs page, a linked markdown file, a pinned issue. Tavily
search + extract fetches them. Everything returned is recorded with its URL so
the writeup can say where each fix's guidance came from. Without a key, the
local fallback file (if any) is used and the record says so.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Guidance:
    query: str
    source: str                      # "tavily" | "local-fallback" | "none"
    urls: list[str] = field(default_factory=list)
    text: str = ""


async def find_guidance(target: str, release: str, symbol: str | None, category: str,
                        fallback: Path | None = None, max_chars: int = 12000) -> Guidance:
    q = f"{target} {release} migration guide {symbol or category} breaking change"
    key = os.environ.get("TAVILY_API_KEY")
    if key:
        try:
            from tavily import AsyncTavilyClient
            client = AsyncTavilyClient(api_key=key)
            res = await client.search(query=q, search_depth="advanced", max_results=5, include_raw_content=True)
            results = res.get("results", [])
            urls = [r["url"] for r in results if r.get("url")]
            chunks = []
            for r in results:
                body = r.get("raw_content") or r.get("content") or ""
                if body:
                    chunks.append(f"--- {r['url']}\n{body[: max_chars // 2]}")
            text = "\n\n".join(chunks)[:max_chars]
            if text:
                return Guidance(query=q, source="tavily", urls=urls, text=text)
        except Exception as e:  # noqa: BLE001 - fall through to the local file, but say why
            note = f"(tavily error: {type(e).__name__}: {e})"
            if fallback and fallback.exists():
                return Guidance(query=q, source="local-fallback " + note, urls=[str(fallback)],
                                text=fallback.read_text(encoding="utf-8")[:max_chars])
            return Guidance(query=q, source="none " + note)
    if fallback and fallback.exists():
        return Guidance(query=q, source="local-fallback", urls=[str(fallback)],
                        text=fallback.read_text(encoding="utf-8")[:max_chars])
    return Guidance(query=q, source="none")


if __name__ == "__main__":
    import sys
    g = asyncio.run(find_guidance("openai", "3.0.0", "httpx", "undeclared-transitive-dependency",
                                  fallback=Path("data/openai-3.0.0/migration_guide.md")))
    print(g.source, g.urls, file=sys.stderr)
    print(g.text[:1500])
