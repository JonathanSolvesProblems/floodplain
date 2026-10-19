"""Run a dependent's test suite before and after a release, in forked sandboxes.

The experiment for one dependent D and one release R of target T:

    base ─── clone D at its tag ─── fresh install, world as of (R.upload - 1 min) ─── pytest   (A)
                      └──────────── fresh install, world as of (R.upload + 1 min) ─── pytest   (B)

Both installs are forks of the same clone checkpoint. `uv pip install
--exclude-newer` makes each fork resolve exactly what `pip install D` would
have resolved at that minute, so an orphaned transitive dependency (the llm
case: httpx stopped arriving via openai) disappears in B the way it did for
real users. A test that passes in A and fails in B was broken by R.

Every run returns a content-addressed image; nothing here is mutable.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from .backends import BASE_OCI, BASE_TAG, OUTPUT_CAP, Backend, ImageRef  # noqa: F401
from .repos import SourceRef

INSTALL_TIMEOUT = 900
TEST_TIMEOUT = 1200

# Extras that conventionally hold test dependencies, tried in order and unioned.
TEST_EXTRAS = ("test", "tests", "testing", "dev", "develop", "all")
# PEP 735 dependency groups, the modern home for the same thing (uv's default for `dev`).
TEST_GROUPS = ("dev", "test", "tests", "testing", "dev-dependencies")

JUNIT_START = "-----FLOODPLAIN-JUNIT-START-----"
JUNIT_END = "-----FLOODPLAIN-JUNIT-END-----"


@dataclass
class RunOutcome:
    label: str                        # "before" or "after"
    cutoff: str                       # RFC 3339 exclude-newer cutoff used
    install_exit: int
    install_tail: str
    test_exit: int | None             # None when install failed
    test_tail: str
    tests: dict[str, str] = field(default_factory=dict)   # test id -> passed|failed|error|skipped
    collection_errors: list[str] = field(default_factory=list)
    resolved: dict[str, str] = field(default_factory=dict) # package -> version actually installed
    elapsed_s: float = 0.0
    cost: float = 0.0
    image_uuid: str | None = None
    backend: str = ""

    @property
    def summary(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for status in self.tests.values():
            out[status] = out.get(status, 0) + 1
        return out


@dataclass
class Experiment:
    dependent: str
    version: str
    source: SourceRef
    before: RunOutcome | None = None
    after: RunOutcome | None = None
    control: RunOutcome | None = None   # a second "before" fork: the flake control
    clone_uuid: str | None = None
    error: str | None = None
    backend: str = ""

    def flaky(self) -> set[str]:
        """Tests that disagreed with themselves across two identical 'before' forks.

        Same checkout, same dependency cutoff, same image: any test whose result differs
        between these two runs is non-deterministic, and cannot be used as evidence that
        the release broke anything.
        """
        if self.before is None or self.control is None:
            return set()
        a, c = self.before.tests, self.control.tests
        return {t for t in set(a) | set(c) if a.get(t) != c.get(t)}

    def verdict(self) -> dict[str, Any]:
        """Deterministic comparison of the forks. No model involved."""
        if self.error or self.before is None or self.after is None:
            return {"status": "not-run", "reason": self.error or "incomplete"}
        a, b = self.before, self.after
        if a.install_exit != 0 and b.install_exit != 0:
            return {"status": "unrunnable", "reason": "install failed before and after"}
        if a.install_exit == 0 and b.install_exit != 0:
            return {"status": "broken", "kind": "install", "reason": "fresh install fails after the release",
                    "evidence": b.install_tail[-2000:]}
        if a.install_exit != 0 and b.install_exit == 0:
            return {"status": "fixed-by-release", "reason": "install failed before, succeeds after"}
        flaky = self.flaky()
        newly_failing = sorted(
            t for t, s in b.tests.items()
            if s in ("failed", "error") and a.tests.get(t) == "passed" and t not in flaky
        )
        new_collection_errors = sorted(set(b.collection_errors) - set(a.collection_errors))
        pre_existing = sorted(
            t for t, s in a.tests.items() if s in ("failed", "error")
        )
        if newly_failing or new_collection_errors:
            return {
                "status": "broken",
                "kind": "tests",
                "newly_failing": newly_failing,
                "new_collection_errors": new_collection_errors,
                "pre_existing_failures": len(pre_existing),
                "excluded_as_flaky": sorted(flaky),
                "flake_control": self.control is not None,
            }
        if not a.tests and not b.tests:
            return {"status": "no-tests", "reason": "no tests collected in either fork",
                    "pre_existing_collection_errors": len(a.collection_errors)}
        return {
            "status": "ok",
            "passed_after": b.summary.get("passed", 0),
            "pre_existing_failures": len(pre_existing),
        }


def _shell_quote(s: str) -> str:
    return "'" + s.replace("'", "'\"'\"'") + "'"


def install_script(extras: tuple[str, ...], cutoff: str, groups: tuple[str, ...] = TEST_GROUPS) -> str:
    """Fresh venv + editable install of /work/repo with the world frozen at `cutoff`.

    A project's test dependencies live in one of two places and modern projects increasingly
    use the second: `[project.optional-dependencies]` (extras, installed as `.[test]`) or
    PEP 735 `[dependency-groups]` (installed as `--group test`). simonw/llm keeps pytest,
    pytest-httpx and its llm-echo test plugin in a `dev` group, so an extras-only installer
    collects zero tests from it. Both are tried, one name at a time so an unknown name is not
    fatal, and the script reports exactly which ones took. The sequence is identical in every
    fork, so any difference between forks comes from the dependency world, not from the recipe.
    """
    extras_list = " ".join(extras)
    groups_list = " ".join(groups)
    return f"""
set -o pipefail
cd /work/repo
uv venv /work/venv --python 3.12 --quiet
export VIRTUAL_ENV=/work/venv PATH=/work/venv/bin:$PATH UV_EXCLUDE_NEWER={cutoff}
export UV_PRERELEASE=allow
uv pip install --quiet -e . 2>/tmp/base.err || {{ echo "[floodplain] base install failed"; tail -n 20 /tmp/base.err; exit 41; }}
took=""
for x in {extras_list}; do
  if uv pip install --quiet -e ".[$x]" 2>/dev/null; then took="$took extra:$x"; fi
done
for g in {groups_list}; do
  if uv pip install --quiet --group "$g" 2>/dev/null; then took="$took group:$g"; fi
done
echo "[floodplain] test deps installed from:$took"
uv pip install --quiet pytest pytest-timeout || exit 42
echo "[floodplain] resolved:"
uv pip freeze | grep -iE '^(openai|httpx|httpx2|certifi|anyio|pydantic|pytest|pytest-httpx|llm-echo|typing-extensions)==' || true
"""


TEST_SCRIPT = f"""
cd /work/repo
export VIRTUAL_ENV=/work/venv PATH=/work/venv/bin:$PATH
export DOWNSTREAM=1 CI=1 PYTHONDONTWRITEBYTECODE=1
timeout {TEST_TIMEOUT - 60} python -m pytest -q -p no:cacheprovider --timeout=300 \\
  --junitxml=/work/junit.xml -o junit_family=xunit2 --maxfail=500 2>&1 | tail -n 200
code=${{PIPESTATUS[0]}}
echo "{JUNIT_START}"; cat /work/junit.xml 2>/dev/null; echo; echo "{JUNIT_END}"
exit $code
"""


def parse_junit(xml_text: str) -> tuple[dict[str, str], list[str]]:
    """Cheap junit parse without an XML dependency: test id -> status, plus collection errors."""
    tests: dict[str, str] = {}
    collection: list[str] = []
    for m in re.finditer(r"<testcase\b([^>]*?)(/>|>(.*?)</testcase>)", xml_text, re.S):
        attrs, _, body = m.group(1), m.group(2), m.group(3) or ""
        cls = re.search(r'classname="([^"]*)"', attrs)
        name = re.search(r'(?<![A-Za-z])name="([^"]*)"', attrs)
        tid = f"{cls.group(1) if cls else ''}::{name.group(1) if name else ''}"
        if "<failure" in body:
            status = "failed"
        elif "<error" in body:
            status = "error"
            if "collection" in body[:400].lower() or (name and "collect" in name.group(1).lower()):
                collection.append(tid)
        elif "<skipped" in body:
            status = "skipped"
        else:
            status = "passed"
        tests[tid] = status
    return tests, collection


def parse_resolved(stdout: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in re.finditer(r"^([A-Za-z0-9_.-]+)==(\S+)$", stdout, re.M):
        out[m.group(1).lower()] = m.group(2)
    return out


def clone_command(source: SourceRef) -> str:
    ref = source.sha or source.tag
    if ref is not None:
        return (
            f"git clone --quiet --filter=blob:none {_shell_quote(source.clone_url)} /work/repo "
            f"&& cd /work/repo && git checkout --quiet {_shell_quote(ref)} && git log -1 --format=%H"
        )
    if source.sdist_url:
        # No git ref matched: unpack the PyPI sdist and make it a git repo so `git diff` still works for fixes.
        return (
            f"mkdir -p /work/sdist && cd /work/sdist && curl -sSL -o src.tar.gz {_shell_quote(source.sdist_url)} "
            f"&& tar xzf src.tar.gz && mv \"$(find . -mindepth 1 -maxdepth 1 -type d | head -n 1)\" /work/repo "
            f"&& cd /work/repo && git init -q && git add -A && git -c user.name=floodplain -c user.email=f@p "
            f"commit -qm sdist && echo sdist:{source.sdist_url}"
        )
    raise ValueError("no tag, sha, or sdist to check out")


class Sandbox:
    """The experiment, expressed against any Backend (Nebius Sandboxes, Serverless Jobs, Docker)."""

    def __init__(self, backend: Backend) -> None:
        self.backend = backend

    @property
    def name(self) -> str:
        return self.backend.name

    async def base_image(self) -> ImageRef:
        return await self.backend.prepare_base()

    async def clone(self, base: ImageRef, source: SourceRef) -> ImageRef:
        res = await self.backend.run(base, clone_command(source), persist=True, timeout=INSTALL_TIMEOUT)
        if not res.ok or res.image is None:
            raise RuntimeError(f"clone failed ({res.exit_code}): {(res.stderr or res.error or '')[-600:]}")
        return res.image

    async def fresh_install_and_test(self, clone_img: ImageRef, label: str, cutoff: datetime) -> RunOutcome:
        cutoff_s = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
        ir = await self.backend.run(clone_img, install_script(TEST_EXTRAS, cutoff_s),
                                    persist=True, timeout=INSTALL_TIMEOUT)
        outcome = RunOutcome(
            label=label, cutoff=cutoff_s, install_exit=ir.exit_code,
            install_tail=(ir.stdout[-4000:] + ir.stderr[-4000:]),
            test_exit=None, test_tail="", elapsed_s=ir.elapsed_s, cost=ir.cost,
            image_uuid=ir.image.id if ir.image else None,
            resolved=parse_resolved(ir.stdout),
            backend=self.backend.name,
        )
        if not ir.ok or ir.image is None:
            return outcome
        tr = await self.backend.run(ir.image, TEST_SCRIPT, persist=False, timeout=TEST_TIMEOUT)
        out = tr.stdout
        xml = ""
        if JUNIT_START in out and JUNIT_END in out:
            xml = out.split(JUNIT_START, 1)[1].split(JUNIT_END, 1)[0]
            out = out.split(JUNIT_START, 1)[0]
        outcome.test_exit = tr.exit_code
        outcome.test_tail = (out + ("\n" + tr.stderr if tr.stderr else ""))[-6000:]
        outcome.tests, outcome.collection_errors = parse_junit(xml)
        outcome.elapsed_s += tr.elapsed_s
        outcome.cost += tr.cost
        return outcome

    async def run_experiment(self, base: ImageRef, dependent: str, version: str, source: SourceRef,
                             release_uploaded: datetime, flake_control: bool = True) -> Experiment:
        """Fork one checkout three ways and run all three at once.

            before   the world one minute before the release
            control  the world one minute before the release, again: identical inputs, so any
                     test that disagrees with `before` is non-deterministic and cannot be
                     evidence of anything
            after    the world one minute after the release

        Without the control arm, a flaky test that happens to fail in `after` looks exactly
        like a break the release caused.
        """
        exp = Experiment(dependent=dependent, version=version, source=source, backend=self.backend.name)
        try:
            clone_img = await self.clone(base, source)
            exp.clone_uuid = clone_img.id
            before_cut = release_uploaded - timedelta(minutes=1)
            after_cut = release_uploaded + timedelta(minutes=1)
            arms = [
                self.fresh_install_and_test(clone_img, "before", before_cut),
                self.fresh_install_and_test(clone_img, "after", after_cut),
            ]
            if flake_control:
                arms.append(self.fresh_install_and_test(clone_img, "control", before_cut))
            results = await asyncio.gather(*arms)
            exp.before, exp.after = results[0], results[1]
            exp.control = results[2] if flake_control else None
        except Exception as e:  # noqa: BLE001 - recorded, never hidden
            exp.error = f"{type(e).__name__}: {e}"[:2000]
        return exp


def experiment_to_json(exp: Experiment) -> dict[str, Any]:
    def outcome(o: RunOutcome | None) -> dict[str, Any] | None:
        if o is None:
            return None
        d = o.__dict__.copy()
        d["summary"] = o.summary
        return d
    return {
        "dependent": exp.dependent,
        "version": exp.version,
        "source": exp.source.__dict__,
        "backend": exp.backend,
        "clone_uuid": exp.clone_uuid,
        "before": outcome(exp.before),
        "after": outcome(exp.after),
        "control": outcome(exp.control),
        "flaky_excluded": sorted(exp.flaky()),
        "verdict": exp.verdict(),
        "error": exp.error,
    }


def dump(exps: list[Experiment]) -> str:
    return json.dumps([experiment_to_json(e) for e in exps], indent=2)
