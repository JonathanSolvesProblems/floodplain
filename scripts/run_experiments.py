"""Run the before/after experiment for every exposed dependent, then triage and fix the broken ones.

    uv run python scripts/run_experiments.py --target openai --release 3.0.0 --stage run --limit 5
    uv run python scripts/run_experiments.py --target openai --release 3.0.0 --only llm --stage all
    uv run python scripts/run_experiments.py --target openai --release 3.0.0 --stage all --concurrency 10

Results land in data/<target>-<release>/experiments/<dependent>.json, one file per
dependent, written as soon as each finishes, so a crashed run resumes where it stopped.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

from floodplain.backends import make_backend
from floodplain.fixer import Fixer
from floodplain.llm import TokenFactory
from floodplain.pypi import PyPI
from floodplain.repos import SourceRef, sdist_url
from floodplain.research import find_guidance
from floodplain.sandbox import Experiment, RunOutcome, Sandbox, experiment_to_json
from floodplain.triage import triage_experiment


def load_experiment(path: Path) -> Experiment:
    d = json.loads(path.read_text(encoding="utf-8"))
    def outcome(o):
        if o is None:
            return None
        o = dict(o); o.pop("summary", None)
        return RunOutcome(**o)
    exp = Experiment(dependent=d["dependent"], version=d["version"], source=SourceRef(**d["source"]),
                     before=outcome(d["before"]), after=outcome(d["after"]),
                     control=outcome(d.get("control")), clone_uuid=d.get("clone_uuid"),
                     error=d.get("error"), backend=d.get("backend", ""))
    return exp


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--release", required=True)
    ap.add_argument("--stage", choices=["run", "triage", "fix", "all"], default="run")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", nargs="*", default=[])
    ap.add_argument("--concurrency", type=int, default=6)
    ap.add_argument("--rerun", action="store_true", help="ignore existing experiment files")
    ap.add_argument("--backend", default=None, help="contree (default) | jobs | docker")
    ap.add_argument("--select", choices=["all", "core", "extra"], default="all",
                    help="all exposed dependents, only those declaring the target as a core "
                         "dependency, or only those declaring it under an extra")
    ap.add_argument("--skip", nargs="*", default=[], help="dependents to leave out, by name")
    ap.add_argument("--trials", type=int, default=1,
                    help="independent fix runs per broken dependent; every trial is recorded")
    args = ap.parse_args()

    root = Path(f"data/{args.target}-{args.release}")
    pop = json.loads((root / "population.json").read_text(encoding="utf-8"))
    release_uploaded = datetime.fromisoformat(pop["meta"]["release_uploaded_at"])
    exp_dir = root / "experiments"
    exp_dir.mkdir(parents=True, exist_ok=True)
    notes_path = root / "release_notes.md"
    notes = notes_path.read_text(encoding="utf-8") if notes_path.exists() else ""

    # Build the runnable list: git ref if resolved, else the PyPI sdist.
    todo: list[tuple[str, str, SourceRef, str]] = []
    async with PyPI() as pypi:
        for e in pop["exposed"]:
            d = e["dependent"]
            if args.only and d["name"] not in args.only:
                continue
            if d["name"] in args.skip:
                continue
            if args.select == "core" and d["via_extra"] is not None:
                continue
            if args.select == "extra" and d["via_extra"] is None:
                continue
            src = SourceRef(**e["source"]) if e["source"] else SourceRef("pypi", d["name"], None, None)
            if not (src.sha or src.tag):
                rel = await pypi.release(d["name"], d["version"])
                src.sdist_url = sdist_url(rel) if rel else None
            if not src.runnable:
                continue
            todo.append((d["name"], d["version"], src, d["requirement"]))
    if args.limit:
        todo = todo[: args.limit]
    print(f"{len(todo)} runnable dependents")

    backend = make_backend(args.backend)
    sandbox = Sandbox(backend)
    print(f"backend: {backend.name}")

    if args.stage in ("run", "all"):
        base = await sandbox.base_image()
        print(f"base image ready: {base}")
        sem = asyncio.Semaphore(args.concurrency)
        t0 = time.time()

        async def one(name, version, src, requirement):
            out = exp_dir / f"{name}.json"
            if out.exists() and not args.rerun:
                return
            async with sem:
                started = time.time()
                exp = await sandbox.run_experiment(base, name, version, src, release_uploaded)
            payload = experiment_to_json(exp)
            payload["requirement"] = requirement
            payload["wall_s"] = round(time.time() - started, 1)
            out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            v = payload["verdict"]
            print(f"  {name:<40} {v.get('status'):<16} {v.get('kind', '')!s:<8} {payload['wall_s']:>7}s", flush=True)

        await asyncio.gather(*(one(*t) for t in todo))
        print(f"run stage done in {time.time() - t0:.0f}s")

    if args.stage in ("triage", "fix", "all"):
        tf = TokenFactory()
        models = await tf.resolve_models()
        print(f"models: {models}")
        fixer = Fixer(tf, backend)
        for name, version, src, requirement in todo:
            path = exp_dir / f"{name}.json"
            if not path.exists():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload["verdict"].get("status") != "broken":
                continue
            exp = load_experiment(path)
            if args.stage in ("triage", "fix", "all") and (not payload.get("triage") or args.rerun):
                tri = await triage_experiment(tf, exp, target=args.target, release=args.release, notes=notes)
                payload["triage"] = tri.to_json() if tri else None
                path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                if tri:
                    print(f"  triage {name:<34} [{tri.category}] {tri.cause[:90]}  quotes={len(tri.quotes)} dropped={tri.dropped_quotes}")
            if args.stage in ("fix", "all") and payload.get("triage") and (not payload.get("fix") or args.rerun):
                from floodplain.triage import Triage
                tri = Triage(**{k: v for k, v in payload["triage"].items()})
                guidance = await find_guidance(args.target, args.release, tri.symbol, tri.category,
                                               fallback=root / "migration_guide.md")
                cutoff = exp.after.cutoff and datetime.strptime(exp.after.cutoff, "%Y-%m-%dT%H:%M:%SZ")
                # Every trial is kept. Nemotron's sampling differs run to run, so one verified patch
                # is a sample, not a behaviour; the page reports verified-in-K-of-N.
                trials = list(payload.get("fix_trials", [])) if not args.rerun else []
                for i in range(args.trials):
                    t0 = time.time()
                    fix = await fixer.fix(exp, tri, target=args.target, release=args.release,
                                          notes=notes + "\n\n# Migration guidance\n" + guidance.text,
                                          after_cutoff=cutoff)
                    rec = fix.to_json()
                    rec["wall_s"] = round(time.time() - t0, 1)
                    rec["trial"] = len(trials) + 1
                    trials.append(rec)
                    status = "VERIFIED" if fix.verified else "not verified"
                    print(f"  fix    {name:<34} trial {rec['trial']}: {status} after {len(fix.attempts)} attempt(s), {rec['wall_s']}s")
                    payload["fix_trials"] = trials
                    first_ok = next((t for t in trials if t["verified"]), None)
                    payload["fix"] = first_ok or trials[-1]
                    payload["guidance"] = {"query": guidance.query, "source": guidance.source, "urls": guidance.urls}
                    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                k = sum(1 for t in trials if t["verified"])
                print(f"  fix    {name:<34} verified in {k} of {len(trials)} trials")
        print(f"token usage: {tf.usage}")


if __name__ == "__main__":
    asyncio.run(main())
