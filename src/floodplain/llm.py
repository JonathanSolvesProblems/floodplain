"""Nemotron on Nebius Token Factory, in three tiers.

    nano  -> fast, cheap: log triage, classification, extraction
    super -> reasoning + code: drafting fixes
    ultra -> frontier reasoning: the escalation when super's fix does not pass

Model IDs are resolved from /v1/models at startup by substring so the code does
not rot when Nebius renames a deployment. Override with FLOODPLAIN_MODEL_NANO,
FLOODPLAIN_MODEL_SUPER, FLOODPLAIN_MODEL_ULTRA.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from openai import AsyncOpenAI

BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
# Measured on 2026-10-19: a trivial prompt spends ~50 completion tokens on reasoning before the
# first content token, so a small max_tokens returns an empty `content` with finish_reason="length".
REASONING_HEADROOM = 2048
Tier = Literal["nano", "super", "ultra"]
TIER_SUBSTRINGS: dict[Tier, tuple[str, ...]] = {
    "nano": ("nemotron-3-nano", "nemotron-nano"),
    "super": ("nemotron-3-super", "nemotron-super"),
    "ultra": ("nemotron-3-ultra", "nemotron-ultra"),
}
# When a tier's model is retired from Token Factory (Nano and Super were scheduled for 9 November
# 2026), use the next tier that is still served rather than failing every run. Each record stores
# the model id that actually ran, so a substitution stays visible in the data.
TIER_FALLBACK: dict[Tier, tuple[Tier, ...]] = {
    "nano": ("super", "ultra"),
    "super": ("ultra",),
    "ultra": ("super",),
}


def reasoning_of(message: Any) -> str:
    """Nemotron returns its chain of thought in `reasoning` (Nano) or `reasoning_content` (Super)."""
    for attr in ("reasoning_content", "reasoning"):
        value = getattr(message, attr, None)
        if value:
            return str(value)
    return ""


@dataclass
class Usage:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    empty_replies: int = 0
    by_model: dict[str, int] = field(default_factory=dict)

    def add(self, model: str, resp: Any) -> None:
        self.calls += 1
        u = getattr(resp, "usage", None)
        if u:
            self.prompt_tokens += u.prompt_tokens or 0
            self.completion_tokens += u.completion_tokens or 0
            details = getattr(u, "completion_tokens_details", None)
            if details is not None and getattr(details, "reasoning_tokens", None):
                self.reasoning_tokens += details.reasoning_tokens
        self.by_model[model] = self.by_model.get(model, 0) + 1


async def _with_backoff(fn, attempts: int = 8):
    """Retry a Token Factory call through 5xx, 429 and connection failures, backing off up to
    about five minutes in total. On 2026-10-24 the endpoint answered 503 to every request,
    authenticated or not, while the status page read operational; the SDK's own three quick
    retries were not enough to ride that out."""
    import asyncio
    import random
    from openai import APIConnectionError, APIStatusError, RateLimitError
    for i in range(attempts):
        try:
            return await fn()
        except (APIConnectionError, RateLimitError) as e:
            last = e
        except APIStatusError as e:
            if e.status_code < 500:
                raise
            last = e
        if i < attempts - 1:
            await asyncio.sleep(min(2 ** i * 2, 90) + random.random())
    raise last


class TokenFactory:
    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or os.environ.get("NEBIUS_API_KEY")
        if not key:
            raise RuntimeError("NEBIUS_API_KEY is not set")
        self.client = AsyncOpenAI(base_url=BASE_URL, api_key=key, timeout=600.0, max_retries=3)
        self.models: dict[Tier, str] = {}
        self.usage = Usage()

    async def resolve_models(self) -> dict[Tier, str]:
        async def listed() -> list[str]:
            return [m.id async for m in self.client.models.list()]
        return self.pick_models(await _with_backoff(listed))

    def pick_models(self, available: list[str]) -> dict[Tier, str]:
        found: dict[Tier, str] = {}
        for tier, needles in TIER_SUBSTRINGS.items():
            override = os.environ.get(f"FLOODPLAIN_MODEL_{tier.upper()}")
            if override:
                found[tier] = override
                continue
            hits = [m for m in available if any(n in m.lower() for n in needles)]
            # Prefer non-quantized, non-VL, non-preview variants when several match.
            hits.sort(key=lambda m: (("fp8" in m.lower()) + ("vl" in m.lower()) + ("omni" in m.lower())
                                     + ("preview" in m.lower()), len(m)))
            if hits:
                found[tier] = hits[0]
        if not found:
            raise RuntimeError(f"no Nemotron model found in Token Factory; available: {available}")
        self.substituted: dict[Tier, Tier] = {}
        for tier in TIER_SUBSTRINGS:
            if tier in found:
                self.models[tier] = found[tier]
                continue
            stand_in = next(t for t in TIER_FALLBACK[tier] + tuple(found) if t in found)
            self.models[tier] = found[stand_in]
            self.substituted[tier] = stand_in
            print(f"  no {tier} Nemotron model is served any more; using {stand_in} ({found[stand_in]}) in its place",
                  flush=True)
        return self.models

    async def chat(self, tier: Tier, system: str, user: str, *, json_mode: bool = False,
                   max_tokens: int = 4096, temperature: float = 0.0) -> str:
        """Nemotron 3 models are reasoning models: they spend completion tokens on a reasoning
        trace delivered in a separate field, and `content` is empty if max_tokens runs out before
        the trace ends. So the budget covers reasoning plus answer, and a truncated reply is
        retried once with a larger budget rather than silently returned blank."""
        model = self.models[tier]
        kwargs: dict[str, Any] = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        budget = max_tokens + REASONING_HEADROOM
        for attempt in range(2):
            resp = await _with_backoff(lambda: self.client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                max_tokens=budget, temperature=temperature, **kwargs,
            ))
            self.usage.add(model, resp)
            choice = resp.choices[0]
            content = (choice.message.content or "").strip()
            if content:
                return content
            self.usage.empty_replies += 1
            if choice.finish_reason != "length" or attempt == 1:
                # Not a budget problem, or already retried: surface whatever the model did say.
                return reasoning_of(choice.message).strip()
            budget *= 3
        return ""

    async def chat_tools(self, tier: Tier, messages: list[dict[str, Any]], tools: list[dict[str, Any]],
                         *, max_tokens: int = 8000, temperature: float = 0.6) -> Any:
        """One turn of a tool-calling conversation. Returns the assistant message, whose
        `tool_calls` (if any) are the model's chosen next actions. A reply truncated before it
        produced either content or a tool call is retried once with a larger budget."""
        model = self.models[tier]
        budget = max_tokens + REASONING_HEADROOM
        for attempt in range(2):
            resp = await _with_backoff(lambda: self.client.chat.completions.create(
                model=model, messages=messages, tools=tools, tool_choice="auto",
                max_tokens=budget, temperature=temperature))
            self.usage.add(model, resp)
            choice = resp.choices[0]
            if choice.message.tool_calls or (choice.message.content or "").strip():
                return choice.message
            self.usage.empty_replies += 1
            if choice.finish_reason != "length" or attempt == 1:
                return choice.message
            budget *= 2
        return choice.message

    async def chat_json(self, tier: Tier, system: str, user: str, **kw: Any) -> dict[str, Any]:
        text = await self.chat(tier, system, user, json_mode=True, **kw)
        return extract_json(text)


def extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    # Nemotron reasoning models may wrap thinking in <think> tags; strip them.
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if m:
        return json.loads(m.group(1))
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return json.loads(text[start:end + 1])
    raise ValueError(f"no JSON object in model output: {text[:300]!r}")


def verified_quotes(quotes: list[str], *sources: str) -> tuple[list[str], list[str]]:
    """Split quotes into those that appear verbatim in a source and those that do not.

    This is the 'nothing invented' rule: an explanation may only cite text that
    is actually in the log. Whitespace is normalized; nothing else is forgiven.
    """
    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", s).strip()
    haystack = " ".join(norm(s) for s in sources)
    kept, dropped = [], []
    for q in quotes:
        (kept if q and norm(q) in haystack else dropped).append(q)
    return kept, dropped
