"""The thing the user walks away holding: a patch per broken dependent, plus a release note.

Downstream is not a scoreboard. The run produces a directory the maintainer can act on:

    out/<target>-<release>/
      patches/<dependent>.patch     a unified diff, produced by `git diff` inside the fork that
                                    went green, never by the model describing its own change
      MIGRATION.md                  the release note, written from the failures that actually
                                    happened, with the fix for each category
      REPORT.md                     who broke, why, and which patch belongs to which project
      UNFIXED.md                    the breaks no patch was verified for, stated plainly

Downstream never opens pull requests against repositories the user does not own. The patches are
handed over; filing them is a human decision, because 157 unsolicited PRs is spam and a maintainer
knows which of their dependents they actually have standing with.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REFUSAL = (
    "Downstream does not open pull requests against repositories you do not own. "
    "Every patch below was verified inside a sandbox by that project's own test suite, "
    "and filing it is your call."
)

CATEGORY_GUIDANCE = {
    "undeclared-transitive-dependency":
        "These projects imported a package that used to arrive through {target} and never declared it. "
        "They are not doing anything wrong, and the import breaks the moment {target} stops carrying it. "
        "State the dropped packages by name at the top of the release note.",
    "removed-or-renamed-api":
        "These projects call something {target} {release} removed or renamed. Give the old name, the new "
        "name, and a line of code for each.",
    "changed-signature-or-behavior":
        "The call still exists but behaves differently. Show the before and after value, not just the signature.",
    "type-or-class-change":
        "An isinstance check, subclass, or exception type changed identity. Name both types.",
    "dependency-conflict":
        "The resolver cannot satisfy these projects' pins alongside {target} {release}.",
    "test-environment":
        "Not caused by the release: network, credentials, or timing.",
}


@dataclass
class BundleStats:
    broken: int
    patched: int
    unpatched: int
    files: list[str]


def _severity(exp: dict[str, Any]) -> tuple[int, int]:
    """Sort key: install breaks first, then by how many tests went red, then by popularity."""
    v = exp.get("verdict", {})
    kind_rank = 0 if v.get("kind") == "install" else 1
    n = len(v.get("newly_failing", [])) + len(v.get("new_collection_errors", []))
    return (kind_rank, -n)


def write_bundle(root: Path, target: str, release: str, experiments: list[dict[str, Any]],
                 population: dict[str, Any]) -> BundleStats:
    out = root / "out" / f"{target}-{release}"
    patches = out / "patches"
    patches.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    broken = [e for e in experiments if e.get("verdict", {}).get("status") == "broken"]
    broken.sort(key=_severity)
    rank = {e["dependent"]["name"]: e["dependent"]["rank"] for e in population.get("exposed", [])}
    downloads = {e["dependent"]["name"]: e["dependent"]["downloads"] for e in population.get("exposed", [])}

    patched, unpatched = [], []
    for e in broken:
        fix = e.get("fix") or {}
        attempt = next((a for a in fix.get("attempts", []) if a.get("verified")), None)
        if attempt and attempt.get("diff", "").strip():
            name = e["dependent"]
            path = patches / f"{name}.patch"
            header = (
                f"# Verified by {name}'s own test suite inside a sandbox fork.\n"
                f"# Break: {target} {release}. Tests that went from passing to failing and now pass again:\n"
            )
            for t in (e["verdict"].get("newly_failing", []) + e["verdict"].get("new_collection_errors", []))[:10]:
                header += f"#   {t}\n"
            header += f"# Proposed by {attempt.get('model', '?')}.\n#\n"
            path.write_text(header + attempt["diff"], encoding="utf-8")
            written.append(str(path.relative_to(root)))
            patched.append((e, attempt))
        else:
            unpatched.append(e)

    # ---- REPORT.md
    lines = [f"# {target} {release}: what it breaks downstream", "",
             f"Generated {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}.", "",
             f"{len(broken)} of {population.get('counts', {}).get('exposed', '?')} exposed dependents broke. "
             f"{len(patched)} have a patch verified green by their own test suite.", "", REFUSAL, "",
             "| Dependent | Downloads/mo | Break | Cause | Patch |", "|---|---|---|---|---|"]
    for e in broken:
        n = e["dependent"]
        tri = e.get("triage") or {}
        v = e["verdict"]
        kind = "install" if v.get("kind") == "install" else f"{len(v.get('newly_failing', []))} tests"
        has = "`patches/%s.patch`" % n if any(x[0]["dependent"] == n for x in patched) else "none verified"
        lines.append(f"| [{n}](https://pypi.org/project/{n}/) | {downloads.get(n, 0):,} | {kind} | "
                     f"{tri.get('category', 'not triaged')} | {has} |")
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    written.append(str((out / "REPORT.md").relative_to(root)))

    # ---- MIGRATION.md: the release note, grouped by what actually happened
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for e in broken:
        by_cat[(e.get("triage") or {}).get("category", "unknown")].append(e)
    m = [f"# Migration notes for {target} {release}", "",
         "Written from the failures that actually occurred when every exposed dependent's own test "
         "suite was run against this release, not from a reading of the diff.", ""]
    for cat, items in sorted(by_cat.items(), key=lambda kv: -len(kv[1])):
        if cat == "test-environment":
            continue
        m.append(f"## {cat.replace('-', ' ')} ({len(items)} projects)")
        m.append("")
        guidance = CATEGORY_GUIDANCE.get(cat, "")
        if guidance:
            m.append(guidance.format(target=target, release=release))
            m.append("")
        symbols = sorted({(e.get("triage") or {}).get("symbol") for e in items if (e.get("triage") or {}).get("symbol")})
        if symbols:
            m.append("Symbols involved: " + ", ".join(f"`{s}`" for s in symbols))
            m.append("")
        for e in items[:12]:
            tri = e.get("triage") or {}
            m.append(f"- **{e['dependent']}** ({downloads.get(e['dependent'], 0):,}/mo): {tri.get('cause', '')}")
        if len(items) > 12:
            m.append(f"- ...and {len(items) - 12} more, listed in REPORT.md")
        m.append("")
    (out / "MIGRATION.md").write_text("\n".join(m) + "\n", encoding="utf-8")
    written.append(str((out / "MIGRATION.md").relative_to(root)))

    # ---- UNFIXED.md: say plainly what has no patch
    u = [f"# Breaks with no verified patch ({len(unpatched)})", "",
         "Downstream reports these rather than shipping a patch it could not prove. A patch is only "
         "written out when the dependent's own suite goes green with it applied and nothing else regresses.", ""]
    for e in unpatched:
        tri = e.get("triage") or {}
        fix = e.get("fix") or {}
        why = "not attempted" if not fix else f"{len(fix.get('attempts', []))} attempt(s), none verified"
        u.append(f"- **{e['dependent']}**: {tri.get('category', 'not triaged')}. {why}.")
    (out / "UNFIXED.md").write_text("\n".join(u) + "\n", encoding="utf-8")
    written.append(str((out / "UNFIXED.md").relative_to(root)))

    return BundleStats(broken=len(broken), patched=len(patched), unpatched=len(unpatched), files=written)


def load_experiments(root: Path, target: str, release: str) -> tuple[list[dict], dict]:
    exp_dir = root / "data" / f"{target}-{release}" / "experiments"
    experiments = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(exp_dir.glob("*.json"))]
    population = json.loads((root / "data" / f"{target}-{release}" / "population.json").read_text(encoding="utf-8"))
    return experiments, population
