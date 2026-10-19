"""Discover who depended on a package on the day a release shipped.

    uv run python scripts/discover.py --target openai --release 3.0.0 --scan 15000

Writes data/<target>-<release>/dependents.json.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
from pathlib import Path

from floodplain.dependents import find_dependents, save
from floodplain.pypi import PyPI, normalize, release_uploaded_at


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--release", required=True, help="the release whose upload time is the cutoff")
    ap.add_argument("--scan", type=int, default=15000, help="how many top packages to inspect")
    args = ap.parse_args()

    target = normalize(args.target)
    async with PyPI() as pypi:
        project = await pypi.project(target)
    if project is None or args.release not in project["releases"]:
        raise SystemExit(f"{target} {args.release} not found on PyPI")
    when = release_uploaded_at(project, args.release)
    print(f"{target} {args.release} uploaded {when.isoformat()}")

    snapshot, deps = await find_dependents(target, when, scan=args.scan)
    core = [d for d in deps if d.via_extra is None]
    print(f"found {len(deps)} dependents in top {args.scan} ({len(core)} core, {len(deps) - len(core)} via extras)")
    for d in deps[:25]:
        tag = "" if d.via_extra is None else f"  [extra: {d.via_extra}]"
        print(f"  #{d.rank:<6} {d.name:<40} {d.version:<14} {d.requirement}{tag}")

    out = Path(f"data/{target}-{args.release}/dependents.json")
    save(deps, out, meta={
        "target": target,
        "release": args.release,
        "release_uploaded_at": when.isoformat(),
        "ranking_snapshot": snapshot,
        "scanned": args.scan,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
    })
    print(f"wrote {out}")


if __name__ == "__main__":
    asyncio.run(main())
