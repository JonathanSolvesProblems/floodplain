"""Split discovered dependents into protected (pinned out of the release) and exposed.

    uv run python scripts/population.py --target openai --release 3.0.0 [--resolve]

--resolve also looks up each exposed dependent's GitHub repo and version tag
(git ls-remote, no API quota) and writes data/<target>-<release>/population.json.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import Version

from downstream.dependents import load
from downstream.repos import resolve_source


def reaches(requirement: str, version: str) -> bool:
    """Would a fresh resolve of this requirement be allowed to pick `version`?"""
    req = Requirement(requirement)
    return req.specifier.contains(Version(version), prereleases=False) if str(req.specifier) else True


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--release", required=True)
    ap.add_argument("--resolve", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="only resolve the first N exposed dependents")
    args = ap.parse_args()

    root = Path(f"data/{args.target}-{args.release}")
    meta, deps = load(root / "dependents.json")

    protected, exposed = [], []
    for d in deps:
        (exposed if reaches(d.requirement, args.release) else protected).append(d)
    exposed_core = [d for d in exposed if d.via_extra is None]
    exposed_extra = [d for d in exposed if d.via_extra is not None]

    print(f"{len(deps)} dependents: {len(protected)} protected by an upper bound, {len(exposed)} exposed "
          f"({len(exposed_core)} core, {len(exposed_extra)} via extras)")
    for name in ("llm", "langroid"):
        hit = next((d for d in deps if d.name == name), None)
        print(f"  {name}: {'#%d %s %s' % (hit.rank, hit.version, hit.requirement) if hit else 'not in top 15000'}")

    records = []
    targets = exposed if not args.limit else exposed[: args.limit]
    if args.resolve:
        sem = asyncio.Semaphore(8)

        async def one(d):
            async with sem:
                src = await resolve_source(d.name, d.version, d.project_urls)
            return d, src

        results = await asyncio.gather(*(one(d) for d in targets))
        with_tag = sum(1 for _, s in results if s and s.tag)
        no_repo = sum(1 for _, s in results if s is None)
        print(f"resolved {with_tag}/{len(results)} to a GitHub tag; {no_repo} have no GitHub URL")
        for d, s in results:
            records.append({
                "dependent": asdict(d),
                "exposed": True,
                "source": None if s is None else asdict(s),
            })
    else:
        records = [{"dependent": asdict(d), "exposed": True, "source": None} for d in targets]

    out = root / "population.json"
    out.write_text(json.dumps({
        "meta": meta,
        "counts": {"total": len(deps), "protected": len(protected), "exposed": len(exposed),
                   "exposed_core": len(exposed_core), "exposed_extra": len(exposed_extra)},
        "protected": [asdict(d) for d in protected],
        "exposed": records,
    }, indent=2), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    asyncio.run(main())
