"""PyPI JSON API client with an on-disk cache.

Everything Downstream knows about a package comes from two public endpoints:

    https://pypi.org/pypi/{name}/json            (all releases, upload times)
    https://pypi.org/pypi/{name}/{version}/json  (that version's requires_dist)

Responses are cached under data/cache/pypi so a discovery scan of 15,000
packages can be re-run without touching the network.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx2
from packaging.requirements import InvalidRequirement, Requirement
from packaging.version import InvalidVersion, Version

USER_AGENT = "downstream/0.1 (+https://github.com/JonathanSolvesProblems)"
CACHE_ROOT = Path("data/cache/pypi")


def normalize(name: str) -> str:
    """PEP 503 name normalization: 'Foo_Bar.baz' -> 'foo-bar-baz'."""
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_upload_time(value: str) -> datetime:
    # PyPI returns "2026-08-12T01:55:48" (naive UTC) or "...Z" in upload_time_iso_8601.
    value = value.rstrip("Z")
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


@dataclass(frozen=True)
class DeclaredDep:
    name: str          # normalized
    spec: str          # the raw requirement string
    extra: str | None  # set when the requirement only applies under an extra


def declared_deps(requires_dist: list[str] | None) -> list[DeclaredDep]:
    out: list[DeclaredDep] = []
    for raw in requires_dist or []:
        try:
            req = Requirement(raw)
        except InvalidRequirement:
            continue
        extra = None
        if req.marker is not None:
            m = re.search(r"extra\s*==\s*['\"]([^'\"]+)['\"]", str(req.marker))
            if m:
                extra = m.group(1)
        out.append(DeclaredDep(name=normalize(req.name), spec=raw, extra=extra))
    return out


def version_at(project: dict, when: datetime) -> str | None:
    """Latest non-prerelease, non-yanked version fully uploaded before `when`."""
    best: tuple[Version, str] | None = None
    for ver_str, files in (project.get("releases") or {}).items():
        if not files:
            continue
        try:
            ver = Version(ver_str)
        except InvalidVersion:
            continue
        if ver.is_prerelease or ver.is_devrelease:
            continue
        if all(f.get("yanked") for f in files):
            continue
        uploaded = max(parse_upload_time(f["upload_time"]) for f in files)
        if uploaded >= when:
            continue
        if best is None or ver > best[0]:
            best = (ver, ver_str)
    return best[1] if best else None


def release_uploaded_at(project: dict, version: str) -> datetime:
    files = project["releases"][version]
    return min(parse_upload_time(f["upload_time"]) for f in files)


class PyPI:
    def __init__(self, cache_root: Path = CACHE_ROOT, concurrency: int = 16) -> None:
        self.cache_root = cache_root
        self.client = httpx2.AsyncClient(
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=30.0,
            follow_redirects=True,
        )
        self.sem = asyncio.Semaphore(concurrency)

    async def aclose(self) -> None:
        await self.client.aclose()

    async def __aenter__(self) -> PyPI:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    def _cache_path(self, name: str, version: str | None) -> Path:
        n = normalize(name)
        if version is None:
            return self.cache_root / n / "project.json"
        return self.cache_root / n / f"{version}.json"

    async def _get(self, url: str, path: Path) -> dict | None:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return None if data == {} else data
        async with self.sem:
            for attempt in range(4):
                try:
                    r = await self.client.get(url)
                except (httpx2.TransportError, httpx2.TimeoutException):
                    await asyncio.sleep(1.5 * (attempt + 1))
                    continue
                if r.status_code == 404:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("{}", encoding="utf-8")
                    return None
                if r.status_code in (429, 500, 502, 503, 504):
                    await asyncio.sleep(2.0 * (attempt + 1))
                    continue
                r.raise_for_status()
                data = r.json()
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(data), encoding="utf-8")
                return data
        raise RuntimeError(f"PyPI gave up on {url}")

    async def project(self, name: str) -> dict | None:
        n = normalize(name)
        return await self._get(f"https://pypi.org/pypi/{n}/json", self._cache_path(n, None))

    async def release(self, name: str, version: str) -> dict | None:
        n = normalize(name)
        return await self._get(
            f"https://pypi.org/pypi/{n}/{version}/json", self._cache_path(n, version)
        )
