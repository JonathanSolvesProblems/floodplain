"""Render one run's results as the Markdown that lands in GitHub: an issue for a release the
watcher checked, or a comment on the pull request that cuts a release candidate.

Everything in it is read from the run's experiment files. A patch is shown only if the
package's own suite passed it in a fork; a break with no verified patch says so.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_URL = "https://github.com/JonathanSolvesProblems/floodplain"
WORKING = ("broken", "ok")


def drop_generated(diff: str) -> str:
    """Remove per-file sections for build metadata from a recorded diff. A run from a PyPI sdist
    tracks its egg-info, which the reinstall regenerates; those sections were never edited."""
    out, keep = [], True
    for line in diff.splitlines(keepends=True):
        if line.startswith("diff --git "):
            keep = ".egg-info/" not in line
        if keep:
            out.append(line)
    return "".join(out)


def load_runs(exp_dir: Path) -> list[dict[str, Any]]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(exp_dir.glob("*.json"))]


def _diff_of(trial: dict[str, Any]) -> str:
    a = next((a for a in trial.get("attempts", []) if a.get("verified")), None)
    return drop_generated(a.get("diff", "")) if a else ""


def _added_lines(trial: dict[str, Any]) -> frozenset[str]:
    """What a verified patch adds and removes, ignoring whitespace and diff headers, so two runs
    that wrote the same change compare equal."""
    return frozenset("".join(l.split()) for l in _diff_of(trial).splitlines()
                     if l[:1] in "+-" and not l.startswith(("+++", "---")))


def round_key(trial: dict[str, Any], fallback: dict[str, Any] | None = None) -> tuple[int, str]:
    """(fixer revision, guidance source) of a trial. Rounds are never pooled: a revision run with
    Tavily's pages and the same revision run with no guidance are two rounds."""
    g = trial.get("guidance") or fallback or {}
    src = (g.get("source") or "none").split(" ")[0]
    return trial.get("fixer_revision", 1), "tavily" if src.startswith("tavily") else src


def best_patch(d: dict[str, Any]) -> tuple[dict[str, Any] | None, int, int]:
    """The patch to hand over, and K of N for the round it comes from.

    The round (one fixer revision with one guidance source) is the one whose trials verified most
    often, the newest on a tie; the patch is the one most of that round's verified runs agreed
    on. A round with no verified trial can only be picked when none has one, so K of N always
    describes one round."""
    trials = d.get("fix_trials") or []
    if not trials:
        return None, 0, 0
    by_round: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for t in trials:
        by_round.setdefault(round_key(t, d.get("guidance")), []).append(t)
    rev = max(by_round, key=lambda r: (sum(1 for t in by_round[r] if t.get("verified")) / len(by_round[r]), r[0]))
    same = by_round[rev]
    won = [t for t in same if t.get("verified")]
    if not won:
        return None, 0, len(same)
    groups: dict[frozenset[str], list[dict[str, Any]]] = {}
    for t in won:
        groups.setdefault(_added_lines(t), []).append(t)
    return max(groups.values(), key=len)[0], len(won), len(same)


def headline(runs: list[dict[str, Any]], target: str, release: str) -> str:
    working = [d for d in runs if d["verdict"].get("status") in WORKING]
    broke = [d for d in working if d["verdict"]["status"] == "broken"]
    if not working:
        return f"{target} {release}: no dependent gave a reading"
    if not broke:
        return f"{target} {release}: none of the {len(working)} working test suites broke"
    return f"{target} {release}: {len(broke)} of the {len(working)} working test suites broke"


def render(runs: list[dict[str, Any]], *, target: str, release: str, released_at: str,
           mode: str = "release", data_path: str = "") -> str:
    """mode: "release" for a published release, "candidate" for an unpublished wheel."""
    working = [d for d in runs if d["verdict"].get("status") in WORKING]
    broke = [d for d in working if d["verdict"]["status"] == "broken"]
    held = [d for d in runs if d["verdict"].get("status") == "held-back"]
    other = len(runs) - len(working) - len(held)
    when = ("as an unpublished wheel, against the index at " if mode == "candidate"
            else "published at ") + released_at
    lines = [f"## {headline(runs, target, release)}", "",
             f"`{target}` {release}, {when}. Each dependent ran its own test suite in three forks of one "
             "checkout on Nebius Sandboxes: the world a minute before, the same again to catch flaky tests, "
             "and a minute after.", ""]
    for d in broke:
        v = d["verdict"]
        n_broke = len(v.get("newly_failing", [])) or len(v.get("new_collection_errors", []))
        before = (d.get("before") or {}).get("summary") or {}
        tri = d.get("triage") or {}
        won, k, n = best_patch(d)
        lines += [f"### {d['dependent']} {d['version']}", "",
                  f"{n_broke} {'modules failed to import' if v.get('new_collection_errors') and not v.get('newly_failing') else 'tests broke'}"
                  f" (it had {before.get('passed', '?')} passing before).", ""]
        if tri.get("cause"):
            lines += [f"**Why** (NVIDIA Nemotron 3 Nano, quoting the log): {tri['cause']}", ""]
            for q in (tri.get("quotes") or [])[:2]:
                lines += [f"> `{q.strip()[:200]}`", ""]
        if won:
            steps = won.get("steps") or []
            kind = "agent runs" if won.get("agent") else "runs of the scripted fixer"
            took = (f" This one took {len(steps)} steps the agent chose: "
                    f"{', '.join(s['tool'] for s in steps[:14])}{', ...' if len(steps) > 14 else ''}." if steps else "")
            lines += [f"**Patch:** passed the package's own suite in a further fork in {k} of {n} independent {kind}.{took}",
                      "", "```diff", _diff_of(won).strip(), "```", ""]
        elif n:
            lines += [f"**No verified patch** in {n} runs; the diagnosis above is what Floodplain can stand behind.", ""]
    if working:
        clean = [d["dependent"] for d in working if d["verdict"]["status"] == "ok"]
        if clean:
            lines += [f"**Read clean ({len(clean)}):** {', '.join(clean)}.", ""]
    flaky = [d for d in working if d["verdict"].get("flaky_after")]
    for d in flaky:
        tests = d["verdict"]["flaky_after"]
        lines += [f"**Not counted:** {d['dependent']} had {len(tests)} test{'s' if len(tests) != 1 else ''} fail once after "
                  f"the release ({', '.join(f'`{t}`' for t in tests[:3])}) that passed when re-run twice in the same "
                  "after fork and once in the before fork, so it is a flaky test, not a break.", ""]
    if held:
        lines += [f"**Held back ({len(held)}):** the release never reached these suites, because another dependency "
                  f"kept {target} at an older version: {', '.join(d['dependent'] for d in held)}.", ""]
    if other:
        lines += [f"{other} more could not be read (no tests shipped, nothing passing before, or the run did not finish).", ""]
    lines += ["---", f"Floodplain does not open pull requests in other people's repositories; it hands over the patch. "
              f"Every figure here is read from the run's results"
              + (f" in [`{data_path}`]({REPO_URL}/tree/master/{data_path})" if data_path else "") + f". [How it works]({REPO_URL})."]
    return "\n".join(lines) + "\n"
