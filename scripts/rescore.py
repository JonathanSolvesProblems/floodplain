"""Recompute every stored verdict from the recorded fork data, without re-running anything.

The arms (install exit, test exit, per-test results) are raw measurements and never change.
The verdict is an interpretation of them, and that interpretation has been tightened several
times. This re-derives it in place so a rule added today applies to runs made yesterday,
and prints what moved.

    uv run python scripts/rescore.py --target openai --release 3.0.0
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from floodplain.repos import SourceRef
from floodplain.sandbox import Experiment, RunOutcome, experiment_to_json


def rebuild(d: dict) -> Experiment:
    def arm(o):
        if o is None:
            return None
        o = {k: v for k, v in o.items() if k != "summary"}
        return RunOutcome(**o)
    return Experiment(
        dependent=d["dependent"], version=d["version"], source=SourceRef(**d["source"]),
        before=arm(d.get("before")), after=arm(d.get("after")), control=arm(d.get("control")),
        clone_uuid=d.get("clone_uuid"), error=d.get("error"), backend=d.get("backend", ""),
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--release", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    root = Path(f"data/{args.target}-{args.release}/experiments")
    moves: Counter[str] = Counter()
    after: Counter[str] = Counter()
    for p in sorted(root.glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        old = d["verdict"].get("status")
        exp = rebuild(d)
        new_payload = experiment_to_json(exp)
        new = new_payload["verdict"].get("status")
        after[new] += 1
        if old != new:
            moves[f"{old} -> {new}"] += 1
            print(f"  {d['dependent']:<34} {old} -> {new}")
        if not args.dry_run:
            # Keep everything the run recorded; replace only the derived fields.
            d["verdict"] = new_payload["verdict"]
            d["flaky_excluded"] = new_payload["flaky_excluded"]
            p.write_text(json.dumps(d, indent=2), encoding="utf-8")

    print("\nchanged:", dict(moves) or "nothing")
    print("now:    ", dict(after))


if __name__ == "__main__":
    main()
