"""Nemotron drafts a fix for a broken dependent and the sandbox decides if it worked.

The loop, per broken dependent:

    installed-after image ── gather context (deps files, grep for the symbol, failing tests)
        └── Nemotron Super proposes search/replace edits
              └── fork: upload edited files, reinstall if metadata changed, run the suite
                    verified = every newly failing test passes and nothing else regressed
    on failure: one more Super attempt with the new log, then one Ultra attempt.

Edits are search/replace blocks that must match exactly once, which LLMs get
right far more often than unified-diff hunk headers. The PR diff is whatever
`git diff` says afterwards, not what the model claims it changed.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any

from .backends import Backend, ImageRef
from .llm import TokenFactory, Tier
from .sandbox import GIT, JUNIT_END, JUNIT_START, TEST_SCRIPT, TEST_TIMEOUT, Experiment, parse_junit
from .triage import Triage

SYSTEM = """You are a senior maintainer fixing a downstream package that broke after an upstream release.
You get: the triage (cause and evidence), the package's dependency declarations, the code that references the failing symbol, and the failing test output.
Propose the smallest change a maintainer would merge. Prefer, in order:
  1. declare a dependency the package already imports but never declared;
  2. migrate the import/call to the upstream's new API when the release notes describe it;
  3. pin the upstream below the breaking version ONLY if 1 and 2 are impossible from the given context.
Never edit tests to make them pass. Never delete a test. Never touch files you were not shown unless creating a new one is unavoidable.
Return one JSON object:
{
  "rationale": "two sentences max",
  "edits": [
    {"path": "relative/path.py", "search": "exact text that appears exactly once in the file", "replace": "replacement text"},
    ...
  ]
}
"search" must be copied verbatim from the file contents shown, including indentation. Keep each search block short (1-15 lines) but unique."""

USER_TEMPLATE = """Upstream: {target} {release}   Downstream: {dependent} {version}
Triage: [{category}] {cause}
Evidence quotes: {quotes}
Suggested plan: {fix_plan}. {fix_notes}
{retry_note}
Upstream release notes (truncated):
{notes}

Dependency declarations and code context from the repository:
{context}

Failing test output (tail):
<log>
{log}
</log>"""

CONTEXT_SCRIPT = r"""
cd /work/repo
echo "=== FILES ==="; git ls-files | head -n 400
for f in pyproject.toml setup.py setup.cfg requirements.txt requirements-dev.txt; do
  if [ -f "$f" ]; then echo "=== $f ==="; head -n 200 "$f"; fi
done
SYMBOL='{symbol}'
if [ -n "$SYMBOL" ]; then
  echo "=== GREP $SYMBOL ==="
  grep -rn --include='*.py' --include='*.toml' --include='*.cfg' --include='*.txt' -E "$SYMBOL" . 2>/dev/null | grep -v '/.venv/' | head -n 80
  for f in $(grep -rl --include='*.py' -E "$SYMBOL" . 2>/dev/null | grep -v '/.venv/' | grep -v '/tests\?/' | head -n 6); do
    echo "=== SOURCE $f ==="; head -n 120 "$f"
  done
fi
"""


@dataclass
class Attempt:
    tier: Tier
    model: str
    rationale: str
    edits: list[dict[str, str]]
    applied: bool
    apply_error: str | None
    install_exit: int | None
    test_exit: int | None
    still_failing: list[str]
    regressions: list[str]
    verified: bool
    diff: str
    elapsed_s: float
    cost: float


@dataclass
class FixResult:
    dependent: str
    attempts: list[Attempt] = field(default_factory=list)

    @property
    def verified(self) -> bool:
        return any(a.verified for a in self.attempts)

    @property
    def best(self) -> Attempt | None:
        return next((a for a in self.attempts if a.verified), None)

    def to_json(self) -> dict[str, Any]:
        return {"dependent": self.dependent, "verified": self.verified,
                "attempts": [asdict(a) for a in self.attempts]}


def apply_edits(files: dict[str, str], edits: list[dict[str, str]]) -> tuple[dict[str, str], str | None]:
    """Apply search/replace edits to in-memory file contents. Each search must match exactly once."""
    out = dict(files)
    for e in edits:
        path, search, replace = e.get("path", ""), e.get("search", ""), e.get("replace", "")
        if path not in out:
            if search.strip() == "":
                out[path] = replace  # new file
                continue
            return files, f"{path}: file was not provided to the model"
        content = out[path]
        n = content.count(search)
        if n != 1:
            # Forgive trailing-whitespace and CRLF drift once, then give up.
            loose = search.rstrip()
            n = content.count(loose) if loose else 0
            if n != 1:
                return files, f"{path}: search block matches {n} times, need exactly 1"
            search = loose
            replace = replace.rstrip()
        out[path] = content.replace(search, replace, 1)
    return out, None


DEP_FILES = ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt")


class Fixer:
    def __init__(self, tf: TokenFactory, backend: Backend) -> None:
        self.tf = tf
        self.backend = backend

    async def gather_context(self, installed: ImageRef, symbol: str | None) -> str:
        sym = re.sub(r"[^A-Za-z0-9_.]", "", symbol or "")
        res = await self.backend.run(installed, CONTEXT_SCRIPT.replace("{symbol}", sym),
                                     persist=False, timeout=180)
        return res.stdout[:60000]

    async def read_files(self, img: ImageRef, paths: list[str]) -> dict[str, str]:
        files: dict[str, str] = {}
        for p in paths:
            try:
                files[p] = (await self.backend.read_file(img, f"/work/repo/{p}")).decode("utf-8", "replace")
            except Exception:  # noqa: BLE001 - a missing file just is not offered to the model
                continue
        return files

    async def propose(self, tier: Tier, exp: Experiment, triage: Triage, *, target: str, release: str,
                      notes: str, context: str, log: str, retry_note: str) -> dict[str, Any]:
        user = USER_TEMPLATE.format(
            target=target, release=release, dependent=exp.dependent, version=exp.version,
            category=triage.category, cause=triage.cause, quotes=json.dumps(triage.quotes[:6]),
            fix_plan=triage.fix_plan, fix_notes=triage.fix_notes, retry_note=retry_note,
            notes=notes[:5000], context=context[:45000], log=log[-6000:],
        )
        return await self.tf.chat_json(tier, SYSTEM, user, max_tokens=6000)

    async def verify(self, installed: ImageRef, edited: dict[str, str], touched_deps: bool,
                     after_cutoff: datetime, verdict: dict[str, Any], baseline_before: dict[str, str]) -> dict[str, Any]:
        upload = {f"/work/repo/{p}": content.encode("utf-8") for p, content in edited.items()}
        reinstall = ""
        if touched_deps:
            cutoff = after_cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
            reinstall = (f"export VIRTUAL_ENV=/work/venv PATH=/work/venv/bin:$PATH UV_EXCLUDE_NEWER={cutoff}; "
                         f"cd /work/repo && (uv pip install --quiet -e . || exit 41); ")
        script = (reinstall + 'cd "$(cat /work/pkgdir 2>/dev/null || echo /work/repo)" && '
                  f"{GIT} diff > /work/fix.diff; " + TEST_SCRIPT)
        r = await self.backend.run(installed, script, files=upload, persist=True, timeout=TEST_TIMEOUT)
        out = r.stdout
        xml = ""
        if JUNIT_START in out and JUNIT_END in out:
            xml = out.split(JUNIT_START, 1)[1].split(JUNIT_END, 1)[0]
            out = out.split(JUNIT_START, 1)[0]
        tests, collection = parse_junit(xml)
        diff = ""
        if r.image is not None:
            try:
                diff = (await self.backend.read_file(r.image, "/work/fix.diff")).decode("utf-8", "replace")
            except Exception:  # noqa: BLE001
                diff = ""
        targets = list(verdict.get("newly_failing", [])) + list(verdict.get("new_collection_errors", []))
        still_failing = [t for t in targets if tests.get(t) != "passed" and t not in collection] if tests else targets
        if verdict.get("kind") == "install":
            still_failing = [] if r.exit_code == 0 or tests else ["install"]
        regressions = sorted(t for t, s in tests.items()
                             if s in ("failed", "error") and baseline_before.get(t) == "passed" and t not in targets)
        verified = (r.exit_code != 41) and not still_failing and not regressions and (bool(tests) or verdict.get("kind") == "install")
        return {"install_exit": 41 if r.exit_code == 41 else 0, "test_exit": r.exit_code, "tests": tests,
                "still_failing": still_failing, "regressions": regressions, "verified": verified,
                "diff": diff, "log": out[-6000:], "elapsed_s": r.elapsed_s, "cost": r.cost}

    async def fix(self, exp: Experiment, triage: Triage, *, target: str, release: str, notes: str,
                  after_cutoff: datetime, plan: tuple[Tier, ...] = ("super", "super", "ultra")) -> FixResult:
        result = FixResult(dependent=exp.dependent)
        verdict = exp.verdict()
        assert exp.after is not None and exp.after.image_uuid and exp.before is not None
        installed_img = ImageRef(exp.after.image_uuid, self.backend.name)
        context = await self.gather_context(installed_img, triage.symbol)
        log = exp.after.test_tail if verdict.get("kind") == "tests" else exp.after.install_tail
        retry_note = ""
        for tier in plan:
            try:
                proposal = await self.propose(tier, exp, triage, target=target, release=release, notes=notes,
                                              context=context, log=log, retry_note=retry_note)
            except Exception as e:  # noqa: BLE001
                result.attempts.append(Attempt(tier, self.tf.models[tier], f"model error: {e}"[:500], [], False,
                                               str(e)[:500], None, None, [], [], False, "", 0.0, 0.0))
                continue
            edits = [e for e in proposal.get("edits", []) if isinstance(e, dict)]
            paths = sorted({e.get("path", "") for e in edits if e.get("path")})
            files = await self.read_files(installed_img, paths)
            edited, err = apply_edits(files, edits)
            if err or not edits:
                err = err or "model returned no edits"
                result.attempts.append(Attempt(tier, self.tf.models[tier], str(proposal.get("rationale", ""))[:500],
                                               edits, False, err, None, None, [], [], False, "", 0.0, 0.0))
                retry_note = f"Your previous edits could not be applied: {err}. Copy search text exactly from the file."
                continue
            changed = {p: c for p, c in edited.items() if files.get(p) != c}
            touched_deps = any(p.split("/")[-1] in DEP_FILES for p in changed)
            v = await self.verify(installed_img, changed, touched_deps, after_cutoff, verdict, exp.before.tests)
            result.attempts.append(Attempt(
                tier, self.tf.models[tier], str(proposal.get("rationale", ""))[:500], edits, True, None,
                v["install_exit"], v["test_exit"], v["still_failing"], v["regressions"], v["verified"],
                v["diff"], v["elapsed_s"], v["cost"],
            ))
            if v["verified"]:
                break
            retry_note = ("Your previous edit was applied but did not fix it. Still failing: "
                          f"{v['still_failing'][:5]}; regressions: {v['regressions'][:5]}. New log tail:\n{v['log'][-3000:]}")
        return result
