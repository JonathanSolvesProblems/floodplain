"""Keep watching a package: every new release is run against the dependents with working suites.

The watch list is the dependents that gave a reading on the base release (their suites ran
and the release reached them, or another dependency held it back). For each new release the
watcher rebuilds the population at that release's upload time: each dependent's version as of
that moment, whether its requirement admits the release, and its source checkout. State lives
in data/watch/<target>.json, so a scheduled run only checks what it has not checked before.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx2
from packaging.requirements import Requirement
from packaging.version import InvalidVersion, Version

from .dependents import _inspect
from .pypi import PyPI, release_uploaded_at
from .repos import github_repo, resolve_source

READING = ("broken", "ok", "held-back")


def state_path(target: str) -> Path:
    return Path("data/watch") / f"{target}.json"


def load_state(target: str, base: str | None = None) -> dict[str, Any]:
    p = state_path(target)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    if not base:
        raise SystemExit(f"no watch state for {target}; start one with --base <release already run>")
    root = Path(f"data/{target}-{base}")
    pop = json.loads((root / "population.json").read_text(encoding="utf-8"))
    rank = {e["dependent"]["name"]: e["dependent"] for e in pop["exposed"]}
    names = []
    for f in sorted((root / "experiments").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d["verdict"].get("status") in READING and d["dependent"] in rank:
            names.append(d["dependent"])
    return {"target": target, "base": base, "ranking_snapshot": pop["meta"]["ranking_snapshot"],
            "dependents": [{"name": n, "rank": rank[n]["rank"], "downloads": rank[n]["downloads"]} for n in names],
            "checked": {}}


def save_state(state: dict[str, Any]) -> None:
    p = state_path(state["target"])
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2), encoding="utf-8")


def fresh_pypi() -> PyPI:
    """Project listings change with every upload, so a watch run never reads an old cache."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return PyPI(cache_root=Path("data/cache/watch") / stamp)


def _final(v: str) -> Version | None:
    try:
        ver = Version(v)
    except InvalidVersion:
        return None
    return None if ver.is_prerelease or ver.is_devrelease else ver


async def unchecked_releases(pypi: PyPI, state: dict[str, Any], latest_only: bool) -> list[tuple[str, datetime]]:
    """Final releases newer than the newest one already checked (or than the base), oldest first."""
    project = await pypi.project(state["target"])
    done = [_final(v) for v in [state["base"], *state["checked"]]]
    floor = max(v for v in done if v is not None)
    new = sorted((ver, v) for v, files in project["releases"].items()
                 if files and (ver := _final(v)) is not None and ver > floor)
    out = [(v, release_uploaded_at(project, v)) for _, v in new]
    return out[-1:] if latest_only else out


def reaches(requirement: str, version: str) -> bool:
    req = Requirement(requirement)
    return req.specifier.contains(Version(version), prereleases=False) if str(req.specifier) else True


async def build_population(pypi: PyPI, state: dict[str, Any], release: str, released_at: datetime) -> Path:
    """data/<target>-<release>/population.json for the watch list, as of the release's upload."""
    target = state["target"]
    exposed, protected = [], []
    for row in state["dependents"]:
        dep = await _inspect(pypi, target, released_at, row["rank"],
                             {"project": row["name"], "download_count": row["downloads"]})
        if dep is None:
            continue
        if not reaches(dep.requirement, release):
            protected.append(asdict(dep))
            continue
        src = await resolve_source(dep.name, dep.version, dep.project_urls)
        exposed.append({"dependent": asdict(dep), "exposed": True, "source": None if src is None else asdict(src)})
    root = Path(f"data/{target}-{release}")
    root.mkdir(parents=True, exist_ok=True)
    meta = {"target": target, "release": release, "release_uploaded_at": released_at.isoformat(),
            "ranking_snapshot": state["ranking_snapshot"], "scanned": len(state["dependents"]),
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "watch_list_from": state["base"]}
    exposed_core = sum(1 for e in exposed if e["dependent"]["via_extra"] is None)
    out = root / "population.json"
    out.write_text(json.dumps({
        "meta": meta,
        "counts": {"total": len(exposed) + len(protected), "protected": len(protected), "exposed": len(exposed),
                   "exposed_core": exposed_core, "exposed_extra": len(exposed) - exposed_core},
        "protected": protected, "exposed": exposed}, indent=2), encoding="utf-8")
    return out


async def fetch_release_notes(pypi: PyPI, target: str, release: str) -> str:
    """The upstream's own GitHub release notes for this version, when it publishes them."""
    project = await pypi.project(target)
    gh = github_repo((project or {}).get("info", {}).get("project_urls") or {})
    if not gh:
        return ""
    owner, repo = gh
    headers = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    async with httpx2.AsyncClient(timeout=30.0, headers=headers) as c:
        for tag in (f"v{release}", release):
            r = await c.get(f"https://api.github.com/repos/{owner}/{repo}/releases/tags/{tag}")
            if r.status_code == 200:
                body = r.json().get("body") or ""
                return f"# {target} {release}\n\n{body}"
    return ""
