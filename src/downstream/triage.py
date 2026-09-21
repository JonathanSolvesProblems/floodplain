"""Nemotron Nano reads a broken fork and says why, citing only what is in the log.

Input: the deterministic verdict (which tests started failing), the after-fork
test output, what the resolver installed before and after, and the release's
own notes. Output: a category, a one-sentence cause, the quotes that prove it,
and a fix plan. Quotes that do not appear verbatim in the log are dropped
before anything is shown, and the number dropped is recorded.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .llm import TokenFactory, verified_quotes
from .sandbox import Experiment

CATEGORIES = (
    "undeclared-transitive-dependency",   # imported something that used to arrive via the target
    "removed-or-renamed-api",             # attribute/import that no longer exists in the target
    "changed-signature-or-behavior",      # call still exists, result or arguments changed
    "type-or-class-change",               # isinstance / subclass / exception type changed
    "dependency-conflict",                # resolver cannot satisfy the dependent's pins after the release
    "test-environment",                   # network, credentials, timing: not caused by the release
    "unknown",
)

SYSTEM = """You are a release engineer explaining why a downstream package's test suite broke after an upstream release.
You will be given: the upstream release, what a fresh install resolved before and after, the tests that newly fail, and the tail of the failing test output.
Rules:
- Cite evidence ONLY by copying exact substrings from the provided log. Never paraphrase inside "quotes".
- If the failures look unrelated to the release (network, credentials, flaky timing), say so with category "test-environment".
- Be specific about the symbol involved (module, attribute, class) when the log shows it.
Answer with one JSON object and nothing else."""

USER_TEMPLATE = """Upstream release: {target} {release}
Downstream package: {dependent} {version} (declares: {requirement})

Resolved BEFORE the release (fresh install, world frozen one minute before):
{resolved_before}

Resolved AFTER the release (fresh install, world frozen one minute after):
{resolved_after}

Deterministic verdict: {verdict}

Upstream release notes (truncated):
{notes}

Tail of the failing test output AFTER the release:
<log>
{log}
</log>

Return JSON with exactly these keys:
{{
  "category": one of {categories},
  "symbol": "the module/attribute/class at the center of the failure, or null",
  "cause": "one sentence, plain language, no speculation beyond the log",
  "quotes": ["exact substrings copied from <log> that prove the cause", "..."],
  "fix_plan": one of ["declare-dependency", "migrate-import", "adapt-call-site", "pin-upstream", "no-fix-needed", "unclear"],
  "fix_notes": "one or two sentences on what a maintainer of the downstream package should change",
  "confidence": number between 0 and 1
}}"""


@dataclass
class Triage:
    dependent: str
    category: str
    symbol: str | None
    cause: str
    quotes: list[str]
    dropped_quotes: int
    fix_plan: str
    fix_notes: str
    confidence: float
    model: str
    raw: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def _fmt_resolved(d: dict[str, str]) -> str:
    return "\n".join(f"  {k}=={v}" for k, v in sorted(d.items())) or "  (nothing recorded)"


async def triage_experiment(tf: TokenFactory, exp: Experiment, *, target: str, release: str,
                            notes: str) -> Triage | None:
    verdict = exp.verdict()
    if verdict.get("status") != "broken" or exp.after is None or exp.before is None:
        return None
    log = exp.after.test_tail if verdict.get("kind") == "tests" else exp.after.install_tail
    user = USER_TEMPLATE.format(
        target=target, release=release, dependent=exp.dependent, version=exp.version,
        requirement=verdict.get("requirement", "see population"),
        resolved_before=_fmt_resolved(exp.before.resolved),
        resolved_after=_fmt_resolved(exp.after.resolved),
        verdict={k: (v[:20] if isinstance(v, list) else v) for k, v in verdict.items()},
        notes=notes[:6000], log=log[-9000:], categories=list(CATEGORIES),
    )
    data = await tf.chat_json("nano", SYSTEM, user, max_tokens=1200)
    quotes = [q for q in data.get("quotes", []) if isinstance(q, str)]
    kept, dropped = verified_quotes(quotes, log, exp.after.install_tail)
    category = data.get("category") if data.get("category") in CATEGORIES else "unknown"
    try:
        confidence = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    return Triage(
        dependent=exp.dependent, category=category, symbol=data.get("symbol") or None,
        cause=str(data.get("cause", "")).strip(), quotes=kept, dropped_quotes=len(dropped),
        fix_plan=str(data.get("fix_plan", "unclear")), fix_notes=str(data.get("fix_notes", "")).strip(),
        confidence=max(0.0, min(1.0, confidence)), model=tf.models["nano"], raw=data,
    )
