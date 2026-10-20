"""Bundle the committed results into site/data.json. Every figure on the page comes from here.

    uv run python scripts/build_site.py --target openai --release 3.0.0

Reads population.json, every experiments/*.json, public_record_strict.json and
maintainer_fixes.json. Writes nothing the page has to interpret: counts, receptor states,
the one-line reason for every non-positive, log excerpts, triage, patches.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path

# Receptor states, in the order the page lists them. Each carries the sentence the page
# shows for every receptor in that state, in the field voice (voice.md).
STATES = {
    "positive":   "Broke. A suite that passed before the release fails after it, and the background sample agrees with the before.",
    "negative":   "Read clean. The suite passed before, passed in the background sample, and still passes after.",
    "no-baseline": "Nothing passed here before the release either, so I cannot say the release changed anything.",
    "no-tests":   "No test suite ships with this package at this version, so there was nothing to hang.",
    "lost":       "The receptor was hung but came back unreadable: the install failed, the run timed out, or the sandbox returned nothing.",
}


def state_of(verdict: dict) -> str:
    s = verdict.get("status")
    if s == "broken":
        return "positive"
    if s == "ok":
        return "negative"
    if s == "no-baseline":
        return "no-baseline"
    if s == "no-tests":
        return "no-tests"
    return "lost"


def why(verdict: dict, d: dict) -> str:
    s = verdict.get("status")
    if s in ("incomplete", "unrunnable", "timed-out", "not-run", "fixed-by-release"):
        if s == "timed-out":
            return "The suite did not finish inside the hour each sandbox operation is allowed."
        if s == "unrunnable":
            return "It would not install in a clean environment before or after the release."
        if s == "fixed-by-release":
            return "It failed to install before the release and installed after it."
        if verdict.get("kind") == "partial-results":
            return (f"The after fork reported {verdict.get('collected_after')} tests against "
                    f"{verdict.get('collected_before')} before, so the run fell over.")
        return "The fork installed but returned no test results."
    return ""


def counts(arm: dict | None) -> dict:
    if not arm:
        return {}
    c = Counter(arm.get("tests", {}).values())
    return {"passed": c.get("passed", 0), "failed": c.get("failed", 0), "error": c.get("error", 0),
            "skipped": c.get("skipped", 0), "collected": len(arm.get("tests", {})),
            "install_exit": arm.get("install_exit"), "test_exit": arm.get("test_exit"),
            "resolved": arm.get("resolved", {})}


def excerpt(tail: str, quotes: list[str], limit: int = 2400) -> str:
    """The stretch of the real log around the evidence, so highlights land on real text."""
    if not tail:
        return ""
    starts = [tail.find(q) for q in quotes if q and tail.find(q) >= 0]
    if not starts:
        return tail[-limit:]
    lo = max(min(starts) - 500, 0)
    return tail[lo:lo + limit]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--release", required=True)
    args = ap.parse_args()
    root = Path(f"data/{args.target}-{args.release}")
    pop = json.loads((root / "population.json").read_text(encoding="utf-8"))
    rec_path = root / "public_record_strict.json"
    record = json.loads(rec_path.read_text(encoding="utf-8")) if rec_path.exists() else {}
    mf_path = root / "maintainer_fixes.json"
    fixes = json.loads(mf_path.read_text(encoding="utf-8")) if mf_path.exists() else {}

    by_name = {e["dependent"]["name"]: e for e in pop["exposed"]}
    receptors = []
    backends = set()
    for p in sorted((root / "experiments").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        backends.add(d.get("backend", ""))
        name = d["dependent"]
        dep = by_name.get(name, {}).get("dependent", {})
        v = d["verdict"]
        st = state_of(v)
        src = d.get("source") or {}
        repo = f"{src.get('owner')}/{src.get('repo')}" if src.get("owner") not in (None, "pypi") else None
        rep = (record.get(repo) or {}).get("first_report") if repo else None
        r = {
            "name": name, "version": d["version"], "rank": dep.get("rank"), "downloads": dep.get("downloads"),
            "requirement": dep.get("requirement"), "via_extra": dep.get("via_extra"),
            "repo": repo, "tag": src.get("tag"), "state": st, "why": why(v, d),
            "before": counts(d.get("before")), "control": counts(d.get("control")), "after": counts(d.get("after")),
            "newly_failing": v.get("newly_failing", []), "new_collection_errors": v.get("new_collection_errors", []),
            "flaky_excluded": v.get("excluded_as_flaky", []), "wall_s": d.get("wall_s"),
            "public_report": rep,
        }
        if st == "positive":
            tri = d.get("triage") or {}
            r["triage"] = {k: tri.get(k) for k in ("category", "symbol", "cause", "quotes", "dropped_quotes",
                                                    "fix_plan", "fix_notes", "model", "confidence")}
            r["log"] = excerpt((d.get("after") or {}).get("test_tail", ""), tri.get("quotes") or [])
            fx = d.get("fix") or {}
            r["fix"] = {
                "verified": fx.get("verified", False),
                "attempts": [{"tier": a["tier"], "model": a["model"], "applied": a["applied"],
                              "verified": a["verified"], "apply_error": a.get("apply_error"),
                              "rationale": a.get("rationale", "")} for a in fx.get("attempts", [])],
                "diff": next((a["diff"] for a in fx.get("attempts", []) if a.get("verified")), ""),
            }
            r["guidance"] = d.get("guidance")
            r["maintainer_fix"] = fixes.get(name)
        receptors.append(r)

    # Position along the reach: upstream (left) is the most downloaded, on a log scale, so the
    # spacing reflects how much of the ecosystem each receptor stands for.
    ranks = [r["rank"] for r in receptors if r["rank"]]
    lo, hi = math.log(min(ranks)), math.log(max(ranks))
    for r in receptors:
        r["reach"] = round((math.log(r["rank"]) - lo) / (hi - lo), 4) if r["rank"] else 1.0

    states = Counter(r["state"] for r in receptors)
    meta = pop["meta"]
    out = {
        "target": args.target, "release": args.release,
        "release_uploaded_at": meta["release_uploaded_at"],
        "ranking_snapshot": meta["ranking_snapshot"], "scanned": meta["scanned"],
        "population": pop["counts"],
        "ran": len(receptors),
        "backends": sorted(b for b in backends if b),
        "states": {k: states.get(k, 0) for k in STATES},
        "state_text": STATES,
        "readable": states.get("positive", 0) + states.get("negative", 0),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "receptors": sorted(receptors, key=lambda r: (r["rank"] or 10**9)),
    }
    site = Path("site")
    site.mkdir(exist_ok=True)
    (site / "data.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"receptors {out['ran']}  states {out['states']}  readable {out['readable']}  backends {out['backends']}")


if __name__ == "__main__":
    main()
