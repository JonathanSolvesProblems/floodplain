"""Fail the build if the prose and the data disagree.

Every number Downstream states in public lives in data/<target>-<release>/stats.json.
This script re-reads that file, pulls every figure out of the README, the writeup and the
demo script, and exits non-zero when any of them no longer matches, or when a number that
was retired reappears somewhere.

    uv run python scripts/check_claims.py

It also enforces two rules that are easy to break by accident at 2am:
  - no headline may be quoted from a run whose backend was not Nebius
  - no claim may cite a count larger than the number of experiments actually run
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROSE_FILES = ["README.md", "WRITEUP.md", "DEMO.md", "out/openai-3.0.0/REPORT.md",
               "out/openai-3.0.0/MIGRATION.md"]

# Numbers that were true at some point and must never reappear once the data moves on.
RETIRED: list[tuple[str, str]] = [
    # (regex, why it was retired)
]

NEBIUS_BACKENDS = {"nebius-sandboxes", "nebius-serverless-jobs"}


class Checker:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.checked = 0

    def check(self, ok: bool, message: str) -> None:
        self.checked += 1
        if not ok:
            self.failures.append(message)

    def report(self) -> int:
        print(f"check_claims: {self.checked} checks, {len(self.failures)} failures")
        for f in self.failures:
            print(f"  FAIL  {f}")
        return 1 if self.failures else 0


def load_stats() -> dict | None:
    candidates = sorted(ROOT.glob("data/*/stats.json"))
    if not candidates:
        return None
    return json.loads(candidates[0].read_text(encoding="utf-8"))


def prose() -> dict[str, str]:
    out = {}
    for rel in PROSE_FILES:
        p = ROOT / rel
        if p.exists():
            out[rel] = p.read_text(encoding="utf-8")
    return out


def main() -> int:
    c = Checker()
    stats = load_stats()
    texts = prose()

    if stats is None:
        print("check_claims: no stats.json yet, nothing to verify against.")
        print("  This is expected before the first full run. It becomes a failure once")
        print("  any prose file quotes a number.")
        quoting = {k: v for k, v in texts.items() if re.search(r"\b\d{2,}\b", v)}
        for name in quoting:
            c.check(False, f"{name} quotes numbers but data/*/stats.json does not exist yet")
        return c.report()

    exp = stats["experiments"]
    pop = stats["population"]

    # 1. The backend behind every quoted headline must be a Nebius one.
    backends = set(exp.get("backends", []))
    if backends:
        c.check(
            backends <= NEBIUS_BACKENDS,
            f"results came from {sorted(backends - NEBIUS_BACKENDS)}, which is not Nebius compute; "
            "a local-docker run may never be the source of a published number",
        )

    # 2. Counts in prose must not exceed what was actually run.
    run = exp["run"]
    for name, text in texts.items():
        for m in re.finditer(r"(\d+)\s+(?:of|/)\s+(\d+)\s+dependents", text):
            num, den = int(m.group(1)), int(m.group(2))
            c.check(num <= den, f"{name}: '{m.group(0)}' has a numerator above its denominator")
            c.check(den <= pop["exposed"],
                    f"{name}: '{m.group(0)}' cites more dependents than the {pop['exposed']} exposed")
        for m in re.finditer(r"ran\s+(\d+)\s+(?:dependents|experiments|suites)", text):
            c.check(int(m.group(1)) <= run,
                    f"{name}: claims {m.group(1)} runs, stats.json records {run}")

    # 3. Headline figures present in prose must match stats.json exactly.
    facts = {
        "broken": exp["broken"],
        "exposed": pop["exposed"],
        "protected": pop["protected"],
        "total_dependents": pop["total"],
        "verified_fixes": stats["fixes"]["verified"],
    }
    for name, text in texts.items():
        for m in re.finditer(r"<!--\s*claim:(\w+)\s*-->\s*(\d[\d,]*)", text):
            key, value = m.group(1), int(m.group(2).replace(",", ""))
            c.check(key in facts, f"{name}: unknown claim key '{key}'")
            if key in facts:
                c.check(facts[key] == value,
                        f"{name}: claim:{key} says {value}, stats.json says {facts[key]}")

    # 4. Retired numbers must not reappear.
    for pattern, why in RETIRED:
        for name, text in texts.items():
            c.check(not re.search(pattern, text), f"{name}: retired claim reappeared ({why})")

    # 5. A fix may only be called verified if the run recorded it as verified.
    for name, text in texts.items():
        if re.search(r"\bverified\b", text, re.I):
            c.check(stats["fixes"]["verified"] > 0,
                    f"{name}: uses the word 'verified' while stats.json records zero verified fixes")

    return c.report()


if __name__ == "__main__":
    sys.exit(main())
