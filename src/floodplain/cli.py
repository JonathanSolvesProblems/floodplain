"""floodplain: test a release against the packages that depend on it, and fix what it breaks.

    floodplain watch  --target openai [--repo OWNER/NAME]
        Every new release since the last one checked: run the dependents' own suites in forked
        Nebius Sandboxes, let the Nemotron agent fix each break, and open a GitHub issue with the
        report. State is kept in data/watch/<target>.json, so a scheduled job only does new work.

    floodplain check  --target openai --wheel dist/openai-X-py3-none-any.whl [--pr N --repo OWNER/NAME]
        The same for a wheel you have not published: the before world is the index now (or
        --as-of), the after world is that plus your wheel. With --pr, the report is posted as a
        comment on the release pull request.

    floodplain report data/openai-3.0.0/experiments --target openai --release 3.0.0
        Print the Markdown report for a finished run.

Needs NEBIUS_API_KEY and NEBIUS_PROJECT_ID (Token Factory); TAVILY_API_KEY is optional; posting
uses the GitHub CLI (`gh`), authenticated as whoever runs it.
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import runner
from .report import headline, load_runs, render
from .watch import (build_population, fetch_release_notes, fresh_pypi, load_state, save_state,
                    unchecked_releases)


def vkey(v: str) -> tuple:
    from packaging.version import Version
    return (Version(v),)


def post(kind: str, repo: str, title: str, body: Path, number: int | None = None) -> str:
    """Write the report into GitHub with the gh CLI. Returns the URL gh prints."""
    if kind == "issue":
        cmd = ["gh", "issue", "create", "--repo", repo, "--title", title, "--body-file", str(body)]
    else:
        cmd = ["gh", "pr", "comment", str(number), "--repo", repo, "--body-file", str(body)]
    out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if out.returncode != 0:
        raise SystemExit(f"posting to GitHub failed: {out.stderr.strip()}")
    return out.stdout.strip().splitlines()[-1] if out.stdout.strip() else ""


async def run_release(target: str, release: str, *, trials: int, concurrency: int, extra: list[str]) -> None:
    common = ["--target", target, "--release", release, "--backend", "contree", *extra]
    await runner.main([*common, "--stage", "run", "--concurrency", str(concurrency)])
    await runner.main([*common, "--stage", "confirm"])
    await runner.main([*common, "--stage", "fix", "--fixer", "agent", "--agent-drafting", "--trials", str(trials)])


async def cmd_watch(a: argparse.Namespace) -> None:
    state = load_state(a.target, a.base)
    async with fresh_pypi() as pypi:
        todo = await unchecked_releases(pypi, state, latest_only=not a.all)
        if not todo:
            print(f"{a.target}: nothing new since {max([state['base'], *state['checked']], key=vkey)}")
            return
        for release, released_at in todo[: a.max_releases]:
            print(f"== {a.target} {release}, uploaded {released_at.isoformat()}")
            pop = await build_population(pypi, state, release, released_at)
            notes = await fetch_release_notes(pypi, a.target, release)
            if notes:
                (pop.parent / "release_notes.md").write_text(notes, encoding="utf-8")
            await run_release(a.target, release, trials=a.trials, concurrency=a.concurrency, extra=[])
            runs = load_runs(pop.parent / "experiments")
            body = pop.parent / "REPORT.md"
            body.write_text(render(runs, target=a.target, release=release,
                                   released_at=released_at.strftime("%Y-%m-%d %H:%M UTC"),
                                   data_path=pop.parent.as_posix()), encoding="utf-8")
            title = headline(runs, a.target, release)
            url = post("issue", a.repo, title, body) if a.repo else ""
            print(f"   {title}" + (f"\n   posted: {url}" if url else ""))
            state["checked"][release] = {"checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                         "headline": title, "issue": url}
            save_state(state)


async def cmd_check(a: argparse.Namespace) -> None:
    state = load_state(a.target, a.base)
    base = a.base or max([state["base"], *state["checked"]], key=vkey)
    as_of = a.as_of or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    names = [d["name"] for d in state["dependents"]]
    extra = ["--candidate", str(a.wheel), "--as-of", as_of, "--only", *names]
    await run_release(a.target, base, trials=a.trials, concurrency=a.concurrency, extra=extra)
    exp_dir = Path(f"data/{a.target}-{base}/candidate/{a.wheel.stem}")
    runs = load_runs(exp_dir)
    version = a.wheel.name.split("-")[1]
    body = exp_dir / "REPORT.md"
    body.write_text(render(runs, target=a.target, release=version, released_at=as_of, mode="candidate",
                           data_path=exp_dir.as_posix()), encoding="utf-8")
    print(headline(runs, a.target, version))
    if a.pr:
        print("posted:", post("comment", a.repo, "", body, a.pr))


def cmd_report(a: argparse.Namespace) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    when = a.released_at
    if not when:
        import json
        pop = Path(f"data/{a.target}-{a.release}/population.json")
        if pop.exists():
            t = datetime.fromisoformat(json.loads(pop.read_text(encoding="utf-8"))["meta"]["release_uploaded_at"])
            when = t.strftime("%Y-%m-%d %H:%M UTC")
    print(render(load_runs(Path(a.dir)), target=a.target, release=a.release, released_at=when or "an unknown time",
                 data_path=a.dir))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="floodplain", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    w = sub.add_parser("watch", help="run every new release of TARGET against its dependents")
    w.add_argument("--target", required=True)
    w.add_argument("--base", help="the release whose dependents form the watch list (first run only)")
    w.add_argument("--repo", help="OWNER/NAME to open the report issue in; omit to only write REPORT.md")
    w.add_argument("--all", action="store_true", help="every unchecked release, not just the newest")
    w.add_argument("--max-releases", type=int, default=3)
    w.add_argument("--trials", type=int, default=3, help="independent agent runs per break")
    w.add_argument("--concurrency", type=int, default=10)

    c = sub.add_parser("check", help="run an unpublished wheel against TARGET's dependents")
    c.add_argument("--target", required=True)
    c.add_argument("--wheel", type=Path, required=True)
    c.add_argument("--base", help="release whose population to use (default: newest watched)")
    c.add_argument("--as-of", help="freeze the before world at this RFC 3339 time (default: now)")
    c.add_argument("--pr", type=int, help="pull request number to comment on")
    c.add_argument("--repo", help="OWNER/NAME of that pull request")
    c.add_argument("--trials", type=int, default=3)
    c.add_argument("--concurrency", type=int, default=10)

    r = sub.add_parser("report", help="print the Markdown report for a finished run")
    r.add_argument("dir")
    r.add_argument("--target", required=True)
    r.add_argument("--release", required=True)
    r.add_argument("--released-at")

    a = ap.parse_args(argv)
    if a.cmd == "watch":
        asyncio.run(cmd_watch(a))
    elif a.cmd == "check":
        if a.pr and not a.repo:
            ap.error("--pr needs --repo")
        asyncio.run(cmd_check(a))
    else:
        cmd_report(a)


if __name__ == "__main__":
    main()
