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
from datetime import datetime, timedelta, timezone
from pathlib import Path

from floodplain.backends import make_backend
from floodplain.agent import AgentResult, FixAgent
from floodplain.fixer import FIXER_REVISION, Fixer

# fixer revisions 3 and 4: Nemotron chooses every step through tools (floodplain/agent.py).
# 4 added run_command, a 40-step budget shown in every tool result, and the triage plan in the brief.
# 5 added a repeat guard, history compaction, a checkpoint every 12 steps, edit hints, temperature 0.6.
# 6 was 5 plus the draft_patch sub-agent tool (--agent-drafting), which no run called.
# 7 names draft_patch in the brief and the checkpoint, and caps run_command at 8 uses a run.
# 8 drafts a whole patch first; the agent starts from it and decides: test, submit, revise or replace.
AGENT_REVISION = 8
from floodplain.llm import TokenFactory
from floodplain.pypi import PyPI
from floodplain.repos import SourceRef, sdist_url
from floodplain.research import Guidance, find_guidance
from floodplain.sandbox import (Experiment, RunOutcome, Sandbox, apply_confirm, attribute, confirm_break,
                                experiment_to_json)
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


async def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--release", required=True)
    ap.add_argument("--stage", choices=["run", "confirm", "triage", "fix", "all"], default="run")
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
    ap.add_argument("--append", action="store_true",
                    help="add --trials more fix trials to the ones already recorded, keeping triage")
    ap.add_argument("--refresh-research", action="store_true",
                    help="ask Tavily again instead of replaying the committed research cache")
    ap.add_argument("--guidance", choices=["auto", "local", "none"], default="auto",
                    help="auto: Tavily pages, else the upstream's own migration guide; local: that guide "
                         "only; none: no migration guidance at all (the ablation, recorded as its own round)")
    ap.add_argument("--fixer", choices=["agent", "scripted"], default="agent",
                    help="agent: Nemotron chooses each step through tools (revision 3); "
                         "scripted: the fixed propose-apply-verify sequence (revisions 1 and 2)")
    ap.add_argument("--agent-tier", choices=["super", "ultra"], default="ultra")
    ap.add_argument("--agent-drafting", action="store_true",
                    help="give the agent the draft_patch sub-agent tool (revision 6)")
    ap.add_argument("--candidate", type=Path, default=None,
                    help="an unreleased wheel of the target: the after fork installs it over the "
                         "before world instead of resolving the published release")
    ap.add_argument("--as-of", default=None,
                    help="with --candidate, the moment the before world is frozen at "
                         "(RFC 3339, default now); results go to <data>/candidate/<wheel>/")
    args = ap.parse_args(argv)

    root = Path(f"data/{args.target}-{args.release}")
    pop = json.loads((root / "population.json").read_text(encoding="utf-8"))
    release_uploaded = datetime.fromisoformat(pop["meta"]["release_uploaded_at"])
    exp_dir = root / "experiments"
    candidate = None
    candidate_version = None
    if args.candidate:
        candidate_version = args.candidate.name.split("-")[1]  # name-version-tags.whl (PEP 427)
        # Pre-release mode: before and control are the world at --as-of; after is that same
        # world plus the wheel. Nothing about the published release is used.
        candidate = (args.candidate.name, args.candidate.read_bytes())
        as_of = (datetime.fromisoformat(args.as_of.replace("Z", "+00:00")) if args.as_of
                 else datetime.now(timezone.utc).replace(microsecond=0))
        release_uploaded = as_of + timedelta(minutes=1)
        exp_dir = root / "candidate" / args.candidate.stem
        print(f"candidate {args.candidate.name}, before world frozen at {as_of.isoformat()}")
    exp_dir.mkdir(parents=True, exist_ok=True)
    notes_path = root / "release_notes.md"
    notes = notes_path.read_text(encoding="utf-8") if notes_path.exists() else ""
    mf_path = root / "maintainer_fixes.json"
    maintainer_fixes = json.loads(mf_path.read_text(encoding="utf-8")) if mf_path.exists() else {}

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
                exp = await sandbox.run_experiment(base, name, version, src, release_uploaded,
                                                   candidate=candidate)
            payload = experiment_to_json(exp)
            # only a fork that actually installed the release can say anything about it
            payload["verdict"] = attribute(payload["verdict"], payload.get("after"), args.target,
                                           candidate_version or args.release)
            payload["requirement"] = requirement
            payload["wall_s"] = round(time.time() - started, 1)
            out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            v = payload["verdict"]
            print(f"  {name:<40} {v.get('status'):<16} {v.get('kind', '')!s:<8} {payload['wall_s']:>7}s", flush=True)

        await asyncio.gather(*(one(*t) for t in todo))
        print(f"run stage done in {time.time() - t0:.0f}s")

    if args.stage in ("confirm", "all"):
        # Every break is re-run before it is believed: its failing tests again on the after image,
        # twice, and once on the before image. Only what reproduces is kept.
        for name, version, src, requirement in todo:
            path = exp_dir / f"{name}.json"
            if not path.exists():
                continue
            d = json.loads(path.read_text(encoding="utf-8"))
            if d["verdict"].get("status") != "broken" or (d.get("confirm") and not args.rerun):
                continue
            c = await confirm_break(backend, d)
            if c is None:
                continue
            d["confirm"] = c
            d["verdict"] = apply_confirm(d["verdict"], c)
            path.write_text(json.dumps(d, indent=2), encoding="utf-8")
            kept = len(c["reproduced_tests"])
            print(f"  confirm {name:<33} {kept} of {len(c['tests'])} reproduced -> {d['verdict']['status']}", flush=True)

    if args.stage in ("triage", "fix", "all"):
        tf = TokenFactory()
        models = await tf.resolve_models()
        print(f"models: {models}")
        fixer = Fixer(tf, backend)
        agent = FixAgent(tf, backend, fixer)
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
            if args.stage in ("fix", "all") and payload.get("triage") and (
                    not payload.get("fix") or args.rerun or args.append):
                from floodplain.triage import Triage
                tri = Triage(**{k: v for k, v in payload["triage"].items()})
                # Research may only see what was public before this dependent's own maintainers
                # acted, and never their own repo; otherwise a matching patch proves nothing.
                mfix = maintainer_fixes.get(name) or {}
                if mfix.get("published_at"):
                    end = datetime.fromisoformat(mfix["published_at"].replace("Z", "+00:00")) - timedelta(days=1)
                else:
                    end = release_uploaded + timedelta(days=1)
                exclude = [f"{exp.source.owner}/{exp.source.repo}"] + ([mfix["repo"]] if mfix.get("repo") else [])
                local_guide = root / "migration_guide.md"
                if args.guidance == "none":
                    # The ablation: the same fixer with the guidance withheld, so its effect can be read
                    # off the rounds instead of assumed.
                    guidance = Guidance(query="", source="none (withheld for this round)")
                elif args.guidance == "local":
                    guidance = Guidance(query="", source="local-fallback (chosen for this round)",
                                        urls=[str(local_guide)], text=local_guide.read_text(encoding="utf-8")[:12000])
                else:
                    guidance = await find_guidance(args.target, args.release, tri.symbol, tri.category,
                                                   fallback=local_guide,
                                                   cache_dir=root / "research", refresh=args.refresh_research,
                                                   exclude_repos=exclude, end_date=end.strftime("%Y-%m-%d"))
                print(f"  guide  {name:<34} {guidance.source} {len(guidance.urls)} page(s)")
                cutoff = exp.after.cutoff and datetime.strptime(exp.after.cutoff, "%Y-%m-%dT%H:%M:%SZ")
                # Every trial is kept. Nemotron's sampling differs run to run, so one verified patch
                # is a sample, not a behaviour; the page reports verified-in-K-of-N.
                trials = list(payload.get("fix_trials", [])) if (args.append or not args.rerun) else []
                for t in trials:  # trials recorded before guidance and revision were kept per trial
                    t.setdefault("guidance", payload.get("guidance"))
                    t.setdefault("fixer_revision", 1)
                g_rec = {"query": guidance.query, "source": guidance.source, "urls": guidance.urls,
                         "fetched_at": guidance.fetched_at,
                         "end_date": guidance.end_date, "excluded": guidance.excluded}
                async def one_trial():
                    t0 = time.time()
                    if args.fixer == "agent":
                        try:
                            fix = await agent.run(exp, tri, target=args.target, release=args.release, notes=notes,
                                                  guidance=guidance.text, guidance_source=guidance.source,
                                                  after_cutoff=cutoff, tier=args.agent_tier,
                                                  drafting=args.agent_drafting, draft_first=args.agent_drafting)
                        except Exception as e:  # noqa: BLE001 - recorded as a failed trial, never hidden
                            fix = AgentResult(name, args.agent_tier, tf.models[args.agent_tier],
                                              ended=f"error: {type(e).__name__}: {e}"[:500])
                        rec = fix.to_json()
                        rec["fixer_revision"] = AGENT_REVISION
                    else:
                        fix = await fixer.fix(exp, tri, target=args.target, release=args.release,
                                              notes=notes + "\n\n# Migration guidance\n" + guidance.text,
                                              after_cutoff=cutoff)
                        rec = fix.to_json()
                        rec["fixer_revision"] = FIXER_REVISION
                    rec["wall_s"] = round(time.time() - t0, 1)
                    rec["guidance"] = g_rec
                    return fix, rec

                # Agent trials are independent sandbox forks, so they run at the same time, and each
                # is written the moment it finishes: a crash loses only the trials still running.
                if args.fixer == "agent":
                    pending = asyncio.as_completed([one_trial() for _ in range(args.trials)])
                else:
                    pending = (one_trial() for _ in range(args.trials))
                for nxt in pending:
                    fix, rec = await nxt
                    rec["trial"] = len(trials) + 1
                    trials.append(rec)
                    status = "VERIFIED" if fix.verified else "not verified"
                    extra = f", {len(rec.get('steps', []))} steps, {rec.get('ended', '')}" if args.fixer == "agent" else ""
                    print(f"  fix    {name:<34} trial {rec['trial']}: {status} after {len(fix.attempts)} attempt(s){extra}, {rec['wall_s']}s")
                    payload["fix_trials"] = trials
                    first_ok = next((t for t in trials if t["verified"]), None)
                    payload["fix"] = first_ok or trials[-1]
                    payload["guidance"] = g_rec
                    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                k = sum(1 for t in trials if t["verified"])
                print(f"  fix    {name:<34} verified in {k} of {len(trials)} trials")
        print(f"token usage: {tf.usage}")


def cli() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    cli()
