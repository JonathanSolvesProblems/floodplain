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
from floodplain.sandbox import Experiment, RunOutcome, apply_confirm, attribute, experiment_to_json


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
    ap.add_argument("--dir", default="experiments", help="experiments, or candidate/<wheel> for a pre-release run")
    args = ap.parse_args()

    root = Path(f"data/{args.target}-{args.release}") / args.dir
    moves: Counter[str] = Counter()
    after: Counter[str] = Counter()
    for p in sorted(root.glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        old = d["verdict"].get("status")
        exp = rebuild(d)
        new_payload = experiment_to_json(exp)
        new_payload["verdict"] = attribute(new_payload["verdict"], d.get("after"), args.target, args.release)
        new_payload["verdict"] = apply_confirm(new_payload["verdict"], d.get("confirm"))
        new = new_payload["verdict"].get("status")
        after[new] += 1
        changed = new_payload["verdict"] != d["verdict"] or new_payload["flaky_excluded"] != d.get("flaky_excluded")
        if old != new:
            moves[f"{old} -> {new}"] += 1
            print(f"  {d['dependent']:<34} {old} -> {new}")
        # Only a file whose derived fields moved is rewritten, so a fix run writing trials into
        # the same files at the same time is never clobbered.
        if changed and not args.dry_run:
            # Keep everything the run recorded; replace only the derived fields.
            d["verdict"] = new_payload["verdict"]
            d["flaky_excluded"] = new_payload["flaky_excluded"]
            p.write_text(json.dumps(d, indent=2), encoding="utf-8")

    print("\nchanged:", dict(moves) or "nothing")
    print("now:    ", dict(after))


if __name__ == "__main__":
    main()
