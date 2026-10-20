"""Bundle the committed results into site/data.json. Every figure on the page comes from here.

    uv run python scripts/build_site.py --target openai --release 3.0.0

Reads population.json, every experiments/*.json, public_record_strict.json and
maintainer_fixes.json. Writes nothing the page has to interpret: counts, receptor states,
the one-line reason for every non-positive, log excerpts, triage, patches.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

# Receptor states, in the order the page lists them. Each carries the sentence the page
# shows for every receptor in that state, in the field voice (voice.md).
STATES = {
    "positive":   "A suite that passed before the release fails after it, and the background sample agrees with the before.",
    "negative":   "The suite passed before, passed again in the background sample, and still passes after.",
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


def test_cells(d: dict, verdict: dict) -> dict:
    """One cell per test that passed before the release, in suite order, grouped by module.

    The detail page draws these: the receptor's sample under the lamp. Codes:
      b  broke: passed before, fails after (or its module no longer imports)
      p  still passes
      f  was already failing before the release (drawn faint, never counted against it)
    A module boundary is a "|" so the grid can leave a gap between modules.
    """
    before = (d.get("before") or {}).get("tests", {})
    after = (d.get("after") or {}).get("tests", {})
    broke = set(verdict.get("newly_failing", []))
    collection_break = bool(verdict.get("new_collection_errors")) and not broke
    def test_file(tid: str) -> str:
        # junit classname is dotted: tests.test_gateway.TestGatewayResource -> tests.test_gateway
        # (the directory is usually "tests", which also starts with "test", so match test_ files)
        parts = tid.split("::")[0].split(".")
        i = next((k for k, p in enumerate(parts) if p.startswith("test_") or p.endswith("_test")), None)
        if i is None:
            i = len(parts) - 2 if len(parts) > 1 and parts[-1][:1].isupper() else len(parts) - 1
        return ".".join(parts[: i + 1])

    files: dict[str, list[str]] = {}
    for tid in sorted(before, key=lambda t: (test_file(t), t)):
        s = before[tid]
        if s in ("failed", "error"):
            code = "f"
        elif s != "passed":
            continue
        elif tid in broke or (collection_break and after.get(tid) != "passed"):
            code = "b"
        else:
            code = "p"
        files.setdefault(test_file(tid), []).append(code)
    rows = [{"file": f.replace(".", "/") + ".py", "codes": "".join(c)} for f, c in files.items()]
    hit = [r for r in rows if "b" in r["codes"]]
    quiet = [r for r in rows if "b" not in r["codes"]]
    allc = "".join(r["codes"] for r in rows)
    return {
        "broke": allc.count("b"), "passed_before": sum(1 for s in before.values() if s == "passed"),
        "already_failing": allc.count("f"), "collection_break": collection_break,
        "files": len(rows), "files_hit": len(hit),
        # files with a break, worst first; the rest are folded into one row
        "hit": sorted(hit, key=lambda r: -r["codes"].count("b")),
        "quiet": {"files": len(quiet), "codes": "".join(r["codes"] for r in quiet)},
    }


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
            r["cells"] = test_cells(d, v)
            tri = d.get("triage") or {}
            r["triage"] = {k: tri.get(k) for k in ("category", "symbol", "cause", "quotes", "dropped_quotes",
                                                    "fix_plan", "fix_notes", "model", "confidence")}
            r["log"] = excerpt((d.get("after") or {}).get("test_tail", ""), tri.get("quotes") or [])
            fx = d.get("fix") or {}
            trials = d.get("fix_trials") or ([fx] if fx else [])

            def attempts_of(t):
                return [{"tier": a["tier"], "model": a["model"], "applied": a["applied"],
                         "verified": a["verified"], "apply_error": a.get("apply_error"),
                         "reasons": a.get("reasons", []), "rationale": a.get("rationale", "")}
                        for a in t.get("attempts", [])]

            r["fix"] = {
                "verified": fx.get("verified", False),
                "attempts": attempts_of(fx),
                "diff": next((a["diff"] for a in fx.get("attempts", []) if a.get("verified")), ""),
                # every independent trial, so the page can say verified in K of N
                "trials": len(trials),
                "trials_verified": sum(1 for t in trials if t.get("verified")),
                "trial_outcomes": [{"trial": t.get("trial", i + 1), "verified": t.get("verified", False),
                                    "attempts": len(t.get("attempts", [])),
                                    "won_by": next((a["tier"] for a in t.get("attempts", []) if a.get("verified")), None),
                                    "wall_s": t.get("wall_s")} for i, t in enumerate(trials)],
            }
            r["guidance"] = d.get("guidance")
            r["maintainer_fix"] = fixes.get(name)
        receptors.append(r)

    # Position along the reach: rank order, most downloaded upstream. A log scale crowded every
    # positive into the last stretch of the river; ordinal spacing says the same thing ("most
    # downloaded first") and gives each receptor room for its own label.
    ordered = sorted(receptors, key=lambda r: (r["rank"] or 10**9, r["name"]))
    for i, r in enumerate(ordered):
        r["reach"] = round(i / max(len(ordered) - 1, 1), 4)

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
