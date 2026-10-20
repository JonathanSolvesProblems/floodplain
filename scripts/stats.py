"""Aggregate experiments + public record into data/<target>-<release>/stats.json.

Every number quoted in the README, the post, and the demo comes from this file,
and check_claims.py fails the build when prose and data disagree.

    uv run python scripts/stats.py --target openai --release 3.0.0
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--release", required=True)
    args = ap.parse_args()
    root = Path(f"data/{args.target}-{args.release}")
    pop = json.loads((root / "population.json").read_text(encoding="utf-8"))
    strict_path = root / "public_record_strict.json"
    strict = json.loads(strict_path.read_text(encoding="utf-8")) if strict_path.exists() else {}

    exps = []
    for p in sorted((root / "experiments").glob("*.json")):
        exps.append(json.loads(p.read_text(encoding="utf-8")))

    status = Counter(e["verdict"].get("status") for e in exps)
    broken = [e for e in exps if e["verdict"].get("status") == "broken"]
    triaged = [e for e in broken if e.get("triage")]
    categories = Counter(e["triage"]["category"] for e in triaged)
    fixed = [e for e in broken if e.get("fix", {}).get("verified")]
    attempts = [len(e["fix"]["attempts"]) for e in broken if e.get("fix")]
    tiers_that_won = Counter(next(a["tier"] for a in e["fix"]["attempts"] if a["verified"]) for e in fixed)
    dropped_quotes = sum(e["triage"]["dropped_quotes"] for e in triaged)
    kept_quotes = sum(len(e["triage"]["quotes"]) for e in triaged)

    # Public record: for each broken dependent, was it reported, and when?
    repo_of = {}
    for e in pop["exposed"]:
        s = e["source"]
        if s:
            repo_of[e["dependent"]["name"]] = f"{s['owner']}/{s['repo']}"
    reported, unreported = [], []
    hours_to_report, hours_to_close = [], []
    for e in broken:
        repo = repo_of.get(e["dependent"])
        fr = strict.get(repo, {}).get("first_report") if repo else None
        if fr:
            reported.append({"dependent": e["dependent"], **fr})
            hours_to_report.append(fr["hours_after_release"])
            if fr["hours_to_close"] is not None:
                hours_to_close.append(fr["hours_to_close"])
        else:
            unreported.append(e["dependent"])

    def median(xs):
        xs = sorted(xs)
        return None if not xs else (xs[len(xs) // 2] if len(xs) % 2 else (xs[len(xs) // 2 - 1] + xs[len(xs) // 2]) / 2)

    wall = [e.get("wall_s", 0) for e in exps]
    cost = sum(sum((e.get(arm) or {}).get("cost", 0) for arm in ("before", "after", "control"))
               for e in exps)
    fix_cost = sum(a["cost"] for e in broken if e.get("fix") for a in e["fix"]["attempts"])

    # Fix trials, one round per (fixer revision, guidance source). Trials from different rounds
    # are never pooled: a K of N always describes one fixer seeing one kind of guidance.
    def round_of(t: dict, e: dict) -> str:
        # trials recorded before guidance was kept per trial ran under the experiment's record
        g = t.get("guidance") or e.get("guidance") or {}
        src = (g.get("source") or "none").split(" ")[0]
        src = "tavily" if src.startswith("tavily") else src
        return f"r{t.get('fixer_revision', 1)}-{src}"

    trials: dict[str, dict[str, dict]] = {}
    for e in broken:
        for t in e.get("fix_trials", []):
            r = trials.setdefault(e["dependent"], {}).setdefault(round_of(t, e), {"k": 0, "n": 0, "verified_diffs": []})
            r["n"] += 1
            if t.get("verified"):
                r["k"] += 1
                won = next(a for a in t["attempts"] if a["verified"])
                r["verified_diffs"].append([l for l in won["diff"].splitlines()
                                            if l.startswith("+") and not l.startswith("+++")][:6])

    # Pre-release check: the same dependents with the release fed in as an unpublished wheel.
    # It only counts as agreeing if every dependent gets the same verdict as the replay.
    candidate = {}
    for cdir in sorted((root / "candidate").glob("*")) if (root / "candidate").exists() else []:
        runs = {json.loads(p.read_text(encoding="utf-8"))["dependent"]: json.loads(p.read_text(encoding="utf-8"))
                for p in cdir.glob("*.json")}
        replay = {e["dependent"]: e["verdict"].get("status") for e in exps}
        cstatus = {d: r["verdict"].get("status") for d, r in runs.items()}
        disagree = sorted(d for d in cstatus if cstatus[d] != replay.get(d))
        candidate[cdir.name] = {
            "run": len(runs), "by_status": dict(Counter(cstatus.values())),
            "broken": sorted(d for d, s in cstatus.items() if s == "broken"),
            "agree_with_replay": len(runs) - len(disagree),
            "disagree": {d: {"candidate": cstatus[d], "replay": replay.get(d)} for d in disagree},
            "as_of": next((r["before"]["cutoff"] for r in runs.values() if r.get("before")), None),
        }

    stats = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "target": args.target, "release": args.release,
        "release_uploaded_at": pop["meta"]["release_uploaded_at"],
        "ranking_snapshot": pop["meta"]["ranking_snapshot"],
        "population": pop["counts"],
        "experiments": {
            "run": len(exps),
            "by_status": dict(status),
            "broken": len(broken),
            "broken_install": sum(1 for e in broken if e["verdict"].get("kind") == "install"),
            "broken_tests": sum(1 for e in broken if e["verdict"].get("kind") == "tests"),
            "median_wall_s": median(wall),
            "total_sandbox_cost": round(cost, 4),
            "backends": sorted({e.get("backend", "") for e in exps if e.get("backend")}),
            "with_flake_control": sum(1 for e in exps if e.get("control")),
            "tests_excluded_as_flaky": sum(len(e.get("flaky_excluded", [])) for e in exps),
        },
        "triage": {
            "triaged": len(triaged),
            "categories": dict(categories),
            "quotes_kept": kept_quotes,
            "quotes_dropped_as_unverifiable": dropped_quotes,
        },
        "fixes": {
            "verified": len(fixed),
            "attempted": sum(1 for e in broken if e.get("fix")),
            "median_attempts": median(attempts),
            "verified_by_tier": dict(tiers_that_won),
            "sandbox_cost": round(fix_cost, 4),
            "trials": trials,
        },
        "readable": status.get("broken", 0) + status.get("ok", 0),
        "candidate": candidate,
        "public_record": {
            "broken_and_reported": len(reported),
            "broken_and_never_reported": len(unreported),
            "unreported_dependents": unreported,
            "median_hours_to_first_report": median(hours_to_report),
            "median_hours_to_close": median(hours_to_close),
            "reports": reported,
        },
    }
    out = root / "stats.json"
    out.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in stats.items() if k != "public_record"}, indent=2))
    print(f"public record: {len(reported)} reported, {len(unreported)} never reported; "
          f"median hours to first report {stats['public_record']['median_hours_to_first_report']}, "
          f"median hours to close {stats['public_record']['median_hours_to_close']}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
