"""Run a dependent's test suite before and after a release, in Nebius Sandboxes.

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

from contree_sdk import Contree

from .repos import SourceRef

BASE_TAG = "downstream-base-py312"
BASE_OCI = "python:3.12-slim-bookworm"
INSTALL_TIMEOUT = 900
TEST_TIMEOUT = 1200
OUTPUT_CAP = 8 * 1024 * 1024

# Extras that conventionally hold test dependencies, tried in order and unioned.
TEST_EXTRAS = ("test", "tests", "testing", "dev", "develop", "all")

JUNIT_START = "-----DOWNSTREAM-JUNIT-START-----"
JUNIT_END = "-----DOWNSTREAM-JUNIT-END-----"


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
    clone_uuid: str | None = None
    error: str | None = None

    def verdict(self) -> dict[str, Any]:
        """Deterministic comparison of the two forks. No model involved."""
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
        newly_failing = sorted(
            t for t, s in b.tests.items() if s in ("failed", "error") and a.tests.get(t) == "passed"
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


def install_script(extras: tuple[str, ...], cutoff: str) -> str:
    """Fresh venv + editable install of /work/repo with the world frozen at `cutoff`."""
    extras_csv = ",".join(extras)
    return f"""
set -o pipefail
cd /work/repo
uv venv /work/venv --python 3.12 --quiet
export VIRTUAL_ENV=/work/venv PATH=/work/venv/bin:$PATH UV_EXCLUDE_NEWER={cutoff}
# Try the test extras first; fall back to a bare install so a missing extra name is not fatal.
if ! uv pip install --quiet -e ".[{extras_csv}]" 2>/tmp/install-extras.err; then
  echo "[downstream] extras install failed, retrying without extras"; tail -n 5 /tmp/install-extras.err
  uv pip install --quiet -e . || exit 41
fi
uv pip install --quiet pytest pytest-timeout || exit 42
echo "[downstream] resolved:"
uv pip freeze | grep -iE '^(openai|httpx|httpx2|anyio|pydantic|typing-extensions)==' || true
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


class Sandbox:
    def __init__(self, sdk: Contree | None = None) -> None:
        self.sdk = sdk or Contree()

    async def base_image(self):
        """python:3.12-slim with git and uv, tagged so every experiment shares it."""
        try:
            img = self.sdk.images.use(BASE_TAG, strict=True)
            return await img if asyncio.iscoroutine(img) else img
        except Exception:
            pass
        base = await self.sdk.images.oci(BASE_OCI)
        built = await base.run(
            shell=(
                "apt-get update -qq && apt-get install -y -qq --no-install-recommends git ca-certificates curl "
                "build-essential >/dev/null && pip install --quiet uv && mkdir -p /work && uv --version"
            ),
            disposable=False,
            tag=BASE_TAG,
            timeout=INSTALL_TIMEOUT,
        )
        return built

    async def clone(self, base, source: SourceRef):
        ref = source.sha or source.tag
        if ref is not None:
            cmd = (
                f"git clone --quiet --filter=blob:none {_shell_quote(source.clone_url)} /work/repo "
                f"&& cd /work/repo && git checkout --quiet {_shell_quote(ref)} && git log -1 --format=%H"
            )
        elif source.sdist_url:
            # No git ref matched: unpack the PyPI sdist and make it a git repo so `git diff` still works for fixes.
            cmd = (
                f"mkdir -p /work/sdist && cd /work/sdist && curl -sSL -o src.tar.gz {_shell_quote(source.sdist_url)} "
                f"&& tar xzf src.tar.gz && mv \"$(find . -mindepth 1 -maxdepth 1 -type d | head -n 1)\" /work/repo "
                f"&& cd /work/repo && git init -q && git add -A && git -c user.name=downstream -c user.email=d@s "
                f"commit -qm sdist && echo sdist:{source.sdist_url}"
            )
        else:
            raise ValueError("no tag, sha, or sdist to check out")
        return await base.run(shell=cmd, disposable=False, timeout=INSTALL_TIMEOUT)

    async def fresh_install_and_test(self, clone_img, label: str, cutoff: datetime) -> RunOutcome:
        cutoff_s = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
        installed = await clone_img.run(
            shell=install_script(TEST_EXTRAS, cutoff_s), disposable=False, timeout=INSTALL_TIMEOUT,
            truncate_output_at=OUTPUT_CAP,
        )
        ir = installed.result
        outcome = RunOutcome(
            label=label, cutoff=cutoff_s, install_exit=ir.exit_code,
            install_tail=(ir.stdout or "")[-4000:] + (ir.stderr or "")[-4000:],
            test_exit=None, test_tail="", elapsed_s=ir.elapsed_time.total_seconds(), cost=ir.cost,
            image_uuid=str(installed.uuid) if installed.uuid else None,
            resolved=parse_resolved(ir.stdout or ""),
        )
        if ir.exit_code != 0:
            return outcome
        tested = await installed.run(
            shell=TEST_SCRIPT, disposable=True, timeout=TEST_TIMEOUT, truncate_output_at=OUTPUT_CAP,
        )
        tr = tested.result
        out = tr.stdout or ""
        xml = ""
        if JUNIT_START in out and JUNIT_END in out:
            xml = out.split(JUNIT_START, 1)[1].split(JUNIT_END, 1)[0]
            out = out.split(JUNIT_START, 1)[0]
        outcome.test_exit = tr.exit_code
        outcome.test_tail = out[-6000:]
        outcome.tests, outcome.collection_errors = parse_junit(xml)
        outcome.elapsed_s += tr.elapsed_time.total_seconds()
        outcome.cost += tr.cost
        return outcome

    async def run_experiment(self, base, dependent: str, version: str, source: SourceRef,
                             release_uploaded: datetime) -> Experiment:
        exp = Experiment(dependent=dependent, version=version, source=source)
        try:
            clone_img = await self.clone(base, source)
            exp.clone_uuid = str(clone_img.uuid) if clone_img.uuid else None
            before_cut = release_uploaded - timedelta(minutes=1)
            after_cut = release_uploaded + timedelta(minutes=1)
            exp.before, exp.after = await asyncio.gather(
                self.fresh_install_and_test(clone_img, "before", before_cut),
                self.fresh_install_and_test(clone_img, "after", after_cut),
            )
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
        "clone_uuid": exp.clone_uuid,
        "before": outcome(exp.before),
        "after": outcome(exp.after),
        "verdict": exp.verdict(),
        "error": exp.error,
    }


def dump(exps: list[Experiment]) -> str:
    return json.dumps([experiment_to_json(e) for e in exps], indent=2)
