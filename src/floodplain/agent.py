"""The fixer as an agent: Nemotron decides every next step; the sandbox decides if it worked.

Fixer revisions 1 and 2 ran a fixed sequence in code (gather context, propose edits, apply,
verify, retry) and the model only filled in the edits. Here the model is handed tools and a
budget, and at every step it chooses what to do from what it just observed:

    list_files   find the files that matter in the package
    read_file    read a slice of a file, numbered, including its own edits so far
    search       grep the checkout for a symbol or an import
    edit_file    a search/replace edit on its working copy
    run_tests    run any subset of the suite in a fresh sandbox fork with its edits applied
    run_command  any shell command in a disposable fork with its edits applied (pip freeze,
                 python -c, a script): the sandbox is isolated, so this is safe to hand over
    submit       send the patch for full verification: a further fork, the whole suite, judged
                 by judge_patch; a rejection comes back with the reasons and the agent goes on
    give_up      stop, saying why

Code enforces only the step budget and the verification gate. Nothing the agent says counts:
a patch is verified only when the package's own suite passes it in a fork, exactly as before.
"""

from __future__ import annotations

import difflib
import json
import re
import shlex
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from .backends import Backend, ImageRef
from .fixer import DEP_FILES, Attempt, Fixer, apply_edits, reinstall_script
from .llm import TokenFactory, Tier
from .sandbox import TEST_TIMEOUT, Experiment
from .triage import Triage

MAX_STEPS = 40
MAX_SUBMITS = 3
RESULT_CAP = 6000
KEEP_FULL = 10
CHECKPOINT = 12
MAX_COMMANDS = 8

SYSTEM = """You are a senior maintainer of a downstream Python package that broke after an upstream release.
Your job: make the package's own test suite pass again with the smallest change a maintainer would merge.
You work in a sandboxed checkout of the package through tools. Decide each next step from what the last tool showed you.

Prefer, in order:
  1. declare a dependency the package already imports but never declared;
  2. migrate the import or call to the upstream's new API, when the release notes or guidance describe it;
  3. pin the upstream below the breaking version, only if 1 and 2 cannot work.
Never edit or delete tests to make them pass. Keep the change small.

Working method: look before you edit (read_file, search), check what is installed with run_command when
it matters (it is limited to a few uses per run), check an idea cheaply with run_tests on the failing test
files, then submit. If draft_patch is available and you know the cause, call it with what you have learned:
it writes a complete candidate patch into your working copy, which you then test and submit or revise. Every tool result
ends with how many steps and submissions you have left; do not spend them all reading. A submitted patch
that is rejected still teaches you something; a run that never submits teaches nothing. submit runs the whole suite in a fresh fork; if it is rejected, read the
reasons, change course, and try again. You have a limited number of steps and submissions. Call give_up
only if you have a reason to believe no small change can work."""

TOOLS: list[dict[str, Any]] = [
    {"type": "function", "function": {
        "name": "list_files", "description": "List tracked files in the package whose path matches a regular expression.",
        "parameters": {"type": "object", "properties": {"pattern": {"type": "string", "description": "regex, e.g. 'pyproject|setup|requirements' or 'test_.*openai'"}},
                       "required": ["pattern"]}}},
    {"type": "function", "function": {
        "name": "read_file", "description": "Read numbered lines of a file in your working copy (your edits included).",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "start": {"type": "integer"}, "end": {"type": "integer"}},
            "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "search", "description": "grep -rn -E over the original checkout (.py, .toml, .cfg, .txt). Returns up to 80 matching lines.",
        "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}, "path": {"type": "string", "description": "optional subdirectory"}},
                       "required": ["pattern"]}}},
    {"type": "function", "function": {
        "name": "edit_file", "description": "Replace text in a file of your working copy. 'search' must appear exactly once (whitespace-tolerant). An empty 'search' on a new path creates the file.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "search": {"type": "string"}, "replace": {"type": "string"}},
            "required": ["path", "search", "replace"]}}},
    {"type": "function", "function": {
        "name": "run_tests", "description": "Run pytest on the given targets (files or node ids) in a fresh sandbox fork with your current edits applied and the package reinstalled if you changed its dependencies. Returns the exit code and the output tail.",
        "parameters": {"type": "object", "properties": {"targets": {"type": "string", "description": "space-separated, e.g. 'tests/test_llm.py tests/test_keys.py'"}},
                       "required": ["targets"]}}},
    {"type": "function", "function": {
        "name": "run_command", "description": "Run a shell command in the package directory, in a disposable sandbox fork with your current edits applied and the package reinstalled if you changed its dependencies (e.g. 'uv pip freeze | grep -i httpx', 'python -c \"import httpx; print(httpx.__version__)\"'). Returns the exit code and output tail.",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {
        "name": "submit", "description": "Submit your current edits for full verification: the whole suite in a fresh fork. Verified only if every test that passed before the release passes again and nothing fails to collect.",
        "parameters": {"type": "object", "properties": {"rationale": {"type": "string", "description": "one or two sentences"}},
                       "required": ["rationale"]}}},
    {"type": "function", "function": {
        "name": "give_up", "description": "Stop without a verified patch.",
        "parameters": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]}}},
]

# Revision 6: a drafting sub-agent the agent may call. Nemotron writes a whole candidate patch from
# the package's dependency files, the code around the failing symbol and the log, plus whatever
# the agent tells it; the patch lands in the agent's working copy for it to test, revise or submit.
DRAFT_TOOL: dict[str, Any] = {"type": "function", "function": {
    "name": "draft_patch", "description": "Ask a drafting model for a complete candidate patch, written from the package's dependency files, the code around the failing symbol and the failing log, plus your notes. It is applied to your working copy and the diff is returned; you decide whether to test, revise or submit it.",
    "parameters": {"type": "object", "properties": {"notes": {"type": "string", "description": "what you have learned so far and what the patch should do or avoid"}},
                   "required": ["notes"]}}}

BRIEF = """Upstream: {target} {release}   Downstream: {dependent} {version}
The package's suite passed before the release and in a second identical "before" fork. After the release:
{summary}
Some of the tests that broke:
{failing}

Triage by Nemotron Nano: [{category}] {cause}
Evidence from the log: {quotes}
Triage's suggested plan: {fix_plan}. {fix_notes}

Failing test output (tail):
<log>
{log}
</log>

Upstream release notes (truncated):
{notes}

Migration guidance ({guidance_source}, truncated):
{guidance}

Start by finding and reading the package's dependency declarations and the code the failures point at."""


def _safe_targets(raw: str) -> str:
    """pytest targets from the model, each shell-quoted; anything that is not a path or node id is dropped."""
    # relative paths or node ids inside the package only: no options, no absolute paths, no ".."
    keep = [t for t in raw.split() if re.fullmatch(r"[\w][\w./:\-\[\],=+@]*", t) and ".." not in t]
    return " ".join(shlex.quote(t) for t in keep[:12])


@dataclass
class Step:
    i: int
    tool: str
    args: dict[str, Any]
    result: str
    elapsed_s: float


@dataclass
class AgentResult:
    dependent: str
    tier: Tier
    model: str
    attempts: list[Attempt] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)
    ended: str = ""

    @property
    def verified(self) -> bool:
        return any(a.verified for a in self.attempts)

    def to_json(self) -> dict[str, Any]:
        return {"dependent": self.dependent, "verified": self.verified, "agent": True,
                "tier": self.tier, "model": self.model, "ended": self.ended,
                "attempts": [asdict(a) for a in self.attempts],
                "steps": [asdict(s) for s in self.steps]}


class FixAgent:
    def __init__(self, tf: TokenFactory, backend: Backend, fixer: Fixer) -> None:
        self.tf, self.backend, self.fixer = tf, backend, fixer

    async def run(self, exp: Experiment, tri: Triage, *, target: str, release: str, notes: str,
                  guidance: str, guidance_source: str, after_cutoff: datetime, tier: Tier = "ultra",
                  max_steps: int = MAX_STEPS, max_submits: int = MAX_SUBMITS,
                  drafting: bool = False, draft_first: bool = False) -> AgentResult:
        assert exp.after is not None and exp.after.image_uuid and exp.before is not None
        verdict = exp.verdict()
        img = ImageRef(exp.after.image_uuid, self.backend.name)
        root = await self.fixer.package_dir(img)
        original: dict[str, str] = {}
        edited: dict[str, str] = {}
        res = AgentResult(exp.dependent, tier, self.tf.models[tier])

        async def load(path: str) -> str | None:
            if path in edited:
                return edited[path]
            if path not in original:
                got = await self.fixer.read_files(img, [path], root)
                if path not in got:
                    return None
                original[path] = got[path]
            return original[path]

        def changed() -> dict[str, str]:
            return {p: c for p, c in edited.items() if original.get(p) != c}

        def touched() -> bool:
            return any(p.split("/")[-1] in DEP_FILES for p in changed())

        async def sandbox(script: str, files: dict[str, bytes] | None = None, timeout: int = 180) -> tuple[int, str]:
            r = await self.backend.run(img, script, persist=False, timeout=timeout, files=files)
            return r.exit_code, (r.stdout + ("\n" + r.stderr if r.stderr else ""))

        cd = 'cd "$(cat /work/pkgdir 2>/dev/null || echo /work/repo)"'

        def nearby(text: str | None, search: str) -> str:
            """The real lines where a failed edit meant to land, numbered, so the next try copies them."""
            if text is None:
                return "The file does not exist; an empty search creates it."
            lines = text.splitlines()
            first = next((ln.strip() for ln in search.splitlines() if ln.strip()), "")
            at = next((k for k, ln in enumerate(lines) if first and first in ln), None)
            if at is None:
                return "Its first line is not in the file. Read the file and copy the text exactly."
            lo, hi = max(0, at - 6), min(len(lines), at + 12)
            body = "\n".join(f"{n + 1:>5}  {lines[n]}" for n in range(lo, hi))
            return f"The file around its first line, exactly as it is now:\n{body}"

        seen: dict[str, str] = {}
        context_cache: list[str] = []
        tools = TOOLS + ([DRAFT_TOOL] if drafting else [])

        async def call(name: str, a: dict[str, Any]) -> tuple[str, bool]:
            """Run one tool. Returns (text for the model, whether the run is over)."""
            if name == "list_files":
                pat = shlex.quote(str(a.get("pattern") or "."))
                _, out = await sandbox(f"{cd} && git -c safe.directory='*' ls-files | grep -iE -- {pat} | head -n 300")
                return out.strip() or "no tracked files match", False
            if name == "read_file":
                text = await load(str(a.get("path", "")))
                if text is None:
                    return f"{a.get('path')}: no such file in the package", False
                lines = text.splitlines()
                start = max(1, int(a.get("start") or 1))
                end = min(len(lines), int(a.get("end") or start + 199), start + 249)
                body = "\n".join(f"{n:>5}  {lines[n - 1]}" for n in range(start, end + 1))
                return f"{a.get('path')} lines {start}-{end} of {len(lines)}\n{body}", False
            if name == "search":
                pat = shlex.quote(str(a.get("pattern") or ""))
                sub = shlex.quote(str(a.get("path") or "."))
                _, out = await sandbox(
                    f"{cd} && grep -rn --include='*.py' --include='*.toml' --include='*.cfg' --include='*.txt' "
                    f"-E -- {pat} {sub} 2>/dev/null | grep -v '/.venv/' | head -n 80")
                return out.strip() or "no matches", False
            if name == "edit_file":
                path = str(a.get("path", ""))
                cur = await load(path)
                files = {path: cur} if cur is not None else {}
                new, err = apply_edits(files, [{"path": path, "search": str(a.get("search", "")),
                                                "replace": str(a.get("replace", ""))}])
                if err:
                    return f"edit not applied: {err}.\n{nearby(cur, str(a.get('search', '')))}", False
                if path not in original:
                    original[path] = cur if cur is not None else ""
                edited[path] = new[path]
                return f"edited {path}; files changed so far: {sorted(changed())}", False
            if name == "run_tests":
                targets = _safe_targets(str(a.get("targets", "")))
                if not targets:
                    return "no valid test targets given", False
                upload = {f"{root}/{p}": c.encode("utf-8") for p, c in changed().items()}
                script = (reinstall_script(touched(), after_cutoff, root)
                          + f"export VIRTUAL_ENV=/work/venv PATH=/work/venv/bin:$PATH FLOODPLAIN=1 CI=1; {cd} && "
                          f"timeout -s INT 900 python -m pytest -q -p no:cacheprovider --timeout=45 "
                          f"--timeout-method=signal {targets} 2>&1 | tail -n 60; exit ${{PIPESTATUS[0]}}")
                code, out = await sandbox(script, upload or None, timeout=1200)
                head = "the patched package would not install" if code == 41 else f"pytest exit {code}"
                return f"{head}\n{out[-4000:]}", False
            if name == "run_command":
                command = str(a.get("command", "")).strip()
                if not command:
                    return "no command given", False
                used = sum(1 for st in res.steps if st.tool == "run_command")
                if used >= MAX_COMMANDS:
                    return (f"run_command is used up ({MAX_COMMANDS} per run). Use what you have learned: edit, "
                            "run_tests, draft_patch if available, or submit."), False
                upload = {f"{root}/{p}": c.encode("utf-8") for p, c in changed().items()}
                script = (reinstall_script(touched(), after_cutoff, root)
                          + f"export VIRTUAL_ENV=/work/venv PATH=/work/venv/bin:$PATH; {cd} && "
                          f"timeout 600 bash -c {shlex.quote(command)} 2>&1 | tail -n 80; exit ${{PIPESTATUS[0]}}")
                code, out = await sandbox(script, upload or None, timeout=900)
                return f"exit {code}\n{out[-4000:]}", False
            if name == "draft_patch":
                if not context_cache:
                    context_cache.append(await self.fixer.gather_context(img, tri.symbol))
                proposal = await self.fixer.propose(
                    tier, exp, tri, target=target, release=release,
                    notes=notes + "\n\n# Migration guidance\n" + guidance, context=context_cache[0],
                    log=(exp.after.test_tail or exp.after.install_tail or ""),
                    retry_note="Notes from the maintainer investigating: " + str(a.get("notes", ""))[:3000])
                edits = [e for e in proposal.get("edits", []) if isinstance(e, dict) and e.get("path")]
                files = {}
                for e in edits:
                    got = await load(e["path"])
                    if got is not None:
                        files[e["path"]] = got
                new, err = apply_edits(files, edits)
                if err or not edits:
                    return f"the draft could not be applied: {err or 'no edits proposed'}", False
                diffs = []
                for path_ in sorted({e["path"] for e in edits}):
                    before = files.get(path_, "")
                    if path_ not in original:
                        original[path_] = before
                    edited[path_] = new[path_]
                    diffs.append("".join(difflib.unified_diff(before.splitlines(True), new[path_].splitlines(True),
                                                              f"a/{path_}", f"b/{path_}")))
                return (f"drafted: {str(proposal.get('rationale', ''))[:400]}\nApplied to your working copy:\n"
                        + "".join(diffs)[:4000]), False
            if name == "submit":
                if not changed():
                    return "nothing to submit: you have not changed any file", False
                n_sub = sum(1 for _ in res.attempts) + 1
                v = await self.fixer.verify(img, changed(), touched(), after_cutoff, verdict, exp.before.tests, root)
                res.attempts.append(Attempt(
                    tier, self.tf.models[tier], str(a.get("rationale", ""))[:500],
                    [{"path": p} for p in sorted(changed())], True, None, v["install_exit"], v["test_exit"],
                    v["still_failing"], v["regressions"], v["verified"], v["diff"], v["elapsed_s"], v["cost"],
                    v["reasons"]))
                if v["verified"]:
                    return "VERIFIED: the whole suite passes in a fresh fork. Done.", True
                left = max_submits - n_sub
                sample = ", ".join(v["still_failing"][:8])
                msg = (f"REJECTED ({'; '.join(v['reasons'])}). Still failing, for example: {sample}. "
                       f"Submissions left: {left}.\nLog tail:\n{v['log'][-2500:]}")
                return msg, left <= 0
            if name == "give_up":
                res.ended = f"gave up: {a.get('reason', '')}"[:500]
                return "stopped", True
            return f"unknown tool {name}", False

        failing = verdict.get("newly_failing", []) or verdict.get("new_collection_errors", [])
        b, aft = exp.before.summary, exp.after.summary
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": BRIEF.format(
                target=target, release=release, dependent=exp.dependent, version=exp.version,
                summary=f"before: {b}; after: {aft}", failing="\n".join(failing[:15]),
                category=tri.category, cause=tri.cause, quotes=json.dumps(tri.quotes[:4]),
                fix_plan=tri.fix_plan, fix_notes=tri.fix_notes,
                log=(exp.after.test_tail or exp.after.install_tail or "")[-5000:],
                notes=notes[:4000], guidance=guidance[:5000], guidance_source=guidance_source)},
        ]
        if draft_first:
            # Revision 8: one Nemotron call drafts a whole patch from the right context before the loop,
            # as the scripted fixer did; the agent starts from that draft and decides what happens to it.
            # In revisions 3 to 7 the agent explored llm's 3,000-line plugin for 40 steps and never
            # submitted (0 of 25), while the same model drafting from context fixed it 9 times in 10.
            t0 = time.monotonic()
            try:
                out, _ = await call("draft_patch", {"notes": ""})
            except Exception as e:  # noqa: BLE001 - a failed draft is an observation, the loop goes on
                out = f"the draft failed: {type(e).__name__}: {e}"[:500]
            res.steps.append(Step(1, "draft_patch", {"notes": "(first draft, before the loop)"}, out[:400],
                                  round(time.monotonic() - t0, 1)))
            messages[1]["content"] += ("\n\nA first draft from the drafting model is already in your working copy:\n"
                                       + out[:RESULT_CAP]
                                       + "\n\nDecide what to do with it: test it on the failing files, submit it, "
                                       "revise it, or discard it and write a different change.")
        idle = 0
        tool_msgs: list[int] = []
        compacted: set[int] = set()
        last_submit = 0
        for i in range(max_steps):
            msg = await self.tf.chat_tools(tier, messages, tools)
            calls = msg.tool_calls or []
            entry: dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
            if calls:
                entry["tool_calls"] = [{"id": c.id, "type": "function",
                                        "function": {"name": c.function.name, "arguments": c.function.arguments or "{}"}}
                                       for c in calls]
            messages.append(entry)
            if not calls:
                idle += 1
                if idle >= 3:
                    res.ended = "stopped answering with tool calls"
                    break
                messages.append({"role": "user", "content": "Use a tool for your next step. Finish with submit, or give_up."})
                continue
            idle = 0
            over = False
            for c in calls:
                try:
                    args = json.loads(c.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                t0 = time.monotonic()
                # The same call with nothing edited since returns what it returned before. Nemotron
                # repeated one command six times in a row in revision 4.
                key = json.dumps([c.function.name, args, sorted(changed().items())], sort_keys=True)
                if c.function.name not in ("submit", "give_up") and key in seen:
                    out, done = ("You already ran exactly this and nothing has changed since, so the result "
                                 "is the same. Choose a different step.\n" + seen[key][:600]), False
                else:
                    try:
                        out, done = await call(c.function.name, args)
                    except Exception as e:  # noqa: BLE001 - a broken tool call is an observation, not a crash
                        out, done = f"tool error: {type(e).__name__}: {e}"[:500], False
                    seen[key] = out
                if c.function.name == "submit":
                    last_submit = i + 1
                res.steps.append(Step(len(res.steps) + 1, c.function.name,
                                      {k: (str(v)[:300]) for k, v in args.items()},
                                      out[:400], round(time.monotonic() - t0, 1)))
                left = max_steps - (i + 1)
                budget = (f"\n[step {i + 1} of {max_steps}; {left} left; "
                          f"submissions left {max_submits - len(res.attempts)}]")
                messages.append({"role": "tool", "tool_call_id": c.id, "content": out[:RESULT_CAP] + budget})
                tool_msgs.append(len(messages) - 1)
                if done:
                    over = True
                    break
            if over:
                break
            # Keep the last KEEP_FULL tool results whole; older ones shrink to their first lines, so
            # the conversation stays readable instead of growing to tens of thousands of tokens.
            for idx in tool_msgs[:-KEEP_FULL]:
                if idx not in compacted:
                    head = "\n".join(messages[idx]["content"].splitlines()[:4])[:400]
                    messages[idx]["content"] = head + "\n[older result shortened]"
                    compacted.add(idx)
            since_submit = (i + 1) - last_submit
            if since_submit and since_submit % CHECKPOINT == 0:
                messages.append({"role": "user", "content": (
                    f"You have used {since_submit} steps since your last submission. In two sentences, state what "
                    "you now believe causes the failure and the smallest change that would fix it. Then make that "
                    "change (or call draft_patch with what you have learned, if you have it) and submit it, unless "
                    "you have evidence it cannot work.")})
        if not res.ended:
            res.ended = "verified" if res.verified else ("out of submissions" if len(res.attempts) >= max_submits
                                                         else "out of steps")
        return res
