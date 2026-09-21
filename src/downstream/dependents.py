"""Discover the packages that depended on a target package on a given date.

Source of the candidate list: hugovk's top-pypi-packages (top 15,000 by
monthly downloads, public, regenerated monthly). For each candidate we resolve
the version that was current on the release date and read THAT version's
requires_dist, so a package that only started depending on the target after
the release does not count, and one that dropped it afterwards still does.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import httpx2

from .pypi import PyPI, declared_deps, normalize, version_at

TOP_PACKAGES_URL = "https://hugovk.github.io/top-pypi-packages/top-pypi-packages.min.json"


@dataclass
class Dependent:
    name: str
    rank: int                 # position in the downloads ranking (1 = most downloaded)
    downloads: int            # monthly downloads per the ranking snapshot
    version: str              # version current on the target's release date
    requirement: str          # the raw requirement string naming the target
    via_extra: str | None     # None when the target is a core dependency
    project_urls: dict[str, str]
    summary: str


async def top_packages(client: httpx2.AsyncClient) -> tuple[str, list[dict]]:
    cache = Path("data/cache/top-pypi-packages.json")
    if cache.exists():
        data = json.loads(cache.read_text(encoding="utf-8"))
    else:
        r = await client.get(TOP_PACKAGES_URL, timeout=60.0)
        r.raise_for_status()
        data = r.json()
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(data), encoding="utf-8")
    return data["last_update"], data["rows"]


async def _inspect(pypi: PyPI, target: str, when: datetime, rank: int, row: dict) -> Dependent | None:
    name = normalize(row["project"])
    project = await pypi.project(name)
    if project is None:
        return None
    version = version_at(project, when)
    if version is None:
        return None
    release = await pypi.release(name, version)
    if release is None:
        return None
    for dep in declared_deps(release["info"].get("requires_dist")):
        if dep.name == target:
            info = release["info"]
            return Dependent(
                name=name,
                rank=rank,
                downloads=int(row["download_count"]),
                version=version,
                requirement=dep.spec,
                via_extra=dep.extra,
                project_urls=info.get("project_urls") or {},
                summary=(info.get("summary") or "")[:200],
            )
    return None


async def find_dependents(
    target: str,
    when: datetime,
    scan: int = 15000,
    progress: bool = True,
) -> tuple[str, list[Dependent]]:
    """Return (ranking_snapshot_date, dependents ordered by downloads)."""
    target = normalize(target)
    async with PyPI() as pypi:
        snapshot, rows = await top_packages(pypi.client)
        rows = [r for r in rows[:scan] if normalize(r["project"]) != target]
        tasks = [
            asyncio.create_task(_inspect(pypi, target, when, rank, row))
            for rank, row in enumerate(rows, start=1)
        ]
        found: list[Dependent] = []
        done = 0
        for coro in asyncio.as_completed(tasks):
            dep = await coro
            done += 1
            if dep is not None:
                found.append(dep)
            if progress and done % 500 == 0:
                print(f"  scanned {done}/{len(tasks)}  dependents so far: {len(found)}", flush=True)
    found.sort(key=lambda d: d.rank)
    return snapshot, found


def save(dependents: list[Dependent], path: Path, meta: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"meta": meta, "dependents": [asdict(d) for d in dependents]}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load(path: Path) -> tuple[dict, list[Dependent]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["meta"], [Dependent(**d) for d in payload["dependents"]]
