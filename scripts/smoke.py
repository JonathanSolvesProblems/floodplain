"""Day-one smoke test. Run this first once NEBIUS_API_KEY (and NEBIUS_PROJECT_ID) exist.

    uv run python scripts/smoke.py

Checks, in order: Token Factory auth and Nemotron model IDs, one Nano call,
Sandboxes auth, base image build, network access inside a sandbox (pip needs
it), and a fork from one checkpoint. Prints cost for each step.
"""

from __future__ import annotations

import asyncio
import os
import time

from contree_sdk import Contree

from downstream.llm import TokenFactory
from downstream.sandbox import BASE_TAG, Sandbox


async def main() -> None:
    for var in ("NEBIUS_API_KEY", "NEBIUS_PROJECT_ID"):
        print(f"{var}: {'set' if os.environ.get(var) else 'MISSING'}")

    print("\n[1] Token Factory models")
    tf = TokenFactory()
    models = await tf.resolve_models()
    for tier, mid in models.items():
        print(f"  {tier:<6} {mid}")
    t0 = time.time()
    reply = await tf.chat("nano", "Answer in five words.", "What does git bisect do?", max_tokens=64)
    print(f"  nano says: {reply.strip()!r}  ({time.time() - t0:.1f}s)")

    print("\n[2] Sandboxes auth")
    sdk = Contree()
    info = await sdk.get_token_info()
    print(f"  token info: {info}")

    print(f"\n[3] Base image ({BASE_TAG})")
    sb = Sandbox(sdk)
    t0 = time.time()
    base = await sb.base_image()
    print(f"  uuid={base.uuid}  ({time.time() - t0:.1f}s)")

    print("\n[4] Network + uv inside the sandbox")
    r = await base.run(shell="uv --version && python -c \"import urllib.request;print(urllib.request.urlopen('https://pypi.org/simple/pip/').status)\"",
                       disposable=True, timeout=120)
    print(f"  exit={r.result.exit_code} cost={r.result.cost} stdout={r.result.stdout.strip()!r} stderr={r.result.stderr.strip()[-300:]!r}")

    print("\n[5] Fork: two children from one checkpoint, in parallel")
    parent = await base.run(shell="echo parent > /work/marker && cat /work/marker", disposable=False, timeout=60)
    a, b = await asyncio.gather(
        parent.run(shell="echo A >> /work/marker && cat /work/marker", disposable=False, timeout=60),
        parent.run(shell="echo B >> /work/marker && cat /work/marker", disposable=False, timeout=60),
    )
    print(f"  parent={parent.uuid}\n  A={a.uuid} -> {a.result.stdout.split()}\n  B={b.uuid} -> {b.result.stdout.split()}")
    print("  fork OK" if a.result.stdout.split() == ["parent", "A"] and b.result.stdout.split() == ["parent", "B"] else "  fork MISMATCH")


if __name__ == "__main__":
    asyncio.run(main())
