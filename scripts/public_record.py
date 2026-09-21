"""Capture the public GitHub record of a release's fallout, per exposed dependent.

    uv run python scripts/public_record.py --target openai --release 3.0.0 --terms httpx2 "openai 3.0.0" "openai<3" "openai>=3" "openai 3"

For each exposed dependent with a GitHub repo, searches issues and pull
requests created on or after the release date that mention any term. The
result is the ground truth the experiment is graded against: which breaks the
ecosystem noticed, when, and how long the fix took. Uses the authenticated
`gh` CLI (30 search requests per minute), so this paces itself.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path


def gh_search(query: str) -> list[dict]:
    cmd = ["gh", "api", "-X", "GET", "search/issues", "-f", f"q={query}", "-f", "per_page=50",
           "--jq", "[.items[] | {number, title, state, created_at, closed_at, html_url, "
                   "is_pr: (.pull_request != null), comments}]"]
    for attempt in range(4):
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if r.returncode == 0:
            return json.loads(r.stdout or "[]")
        if "rate limit" in (r.stderr or "").lower() or "403" in (r.stderr or ""):
            time.sleep(30 * (attempt + 1))
            continue
        raise RuntimeError(r.stderr.strip()[:500])
    return []


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--release", required=True)
    ap.add_argument("--terms", nargs="+", required=True)
    ap.add_argument("--extra-repos", nargs="*", default=[], help="owner/repo not in the population (e.g. langroid/langroid)")
    args = ap.parse_args()

    root = Path(f"data/{args.target}-{args.release}")
    pop = json.loads((root / "population.json").read_text(encoding="utf-8"))
    since = pop["meta"]["release_uploaded_at"][:10]

    repos: list[tuple[str, str]] = []
    for e in pop["exposed"]:
        s = e["source"]
        if s:
            repos.append((e["dependent"]["name"], f"{s['owner']}/{s['repo']}"))
    for extra in args.extra_repos:
        repos.append((extra.split("/")[1], extra))
    # Monorepos appear several times; search each repo once.
    seen: dict[str, list[str]] = {}
    for name, repo in repos:
        seen.setdefault(repo, []).append(name)

    terms = " OR ".join(f'"{t}"' if " " in t or any(c in t for c in "<>=") else t for t in args.terms)
    out_path = root / "public_record.json"
    record = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}

    print(f"searching {len(seen)} repos for ({terms}) created:>={since}")
    for i, (repo, names) in enumerate(seen.items(), start=1):
        if repo in record:
            continue
        q = f"repo:{repo} ({terms}) created:>={since}"
        try:
            hits = gh_search(q)
        except RuntimeError as err:
            hits = [{"error": str(err)}]
        record[repo] = {"dependents": names, "query": q, "hits": hits,
                        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds")}
        n = len([h for h in hits if "error" not in h])
        flag = f"  <-- {n} hit(s)" if n else ""
        print(f"  [{i}/{len(seen)}] {repo}{flag}", flush=True)
        out_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
        time.sleep(2.2)  # 30 requests/minute for authenticated search

    total_hits = sum(len([h for h in r["hits"] if "error" not in h]) for r in record.values())
    repos_with_hits = sum(1 for r in record.values() if any("error" not in h for h in r["hits"]))
    print(f"{repos_with_hits} repos with public mentions, {total_hits} issues/PRs total -> {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
