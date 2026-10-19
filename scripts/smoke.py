"""Day-one smoke test. Run this first, and again the moment Sandboxes access is granted.

    uv run python scripts/smoke.py                  # default backend (Nebius Sandboxes)
    uv run python scripts/smoke.py --backend docker # local, for development

Checks in order: Token Factory auth and Nemotron model ids, one call per tier, backend auth,
base image, network inside the sandbox (pip needs it), and a three-way fork from one
checkpoint. Prints cost and elapsed time for each step.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import time

from floodplain.backends import make_backend
from floodplain.llm import TokenFactory


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default=None, help="contree (default) | jobs | docker")
    ap.add_argument("--skip-models", action="store_true")
    args = ap.parse_args()

    for var in ("NEBIUS_API_KEY", "NEBIUS_PROJECT_ID"):
        print(f"{var}: {'set' if os.environ.get(var) else 'MISSING'}")

    if not args.skip_models:
        print("\n[1] Token Factory: Nemotron model ids")
        tf = TokenFactory()
        models = await tf.resolve_models()
        for tier, mid in models.items():
            print(f"  {tier:<6} {mid}")
        for tier in ("nano", "super"):
            t0 = time.time()
            reply = await tf.chat(tier, "Answer in five words or fewer.",
                                  "What does a dependency lockfile pin?", max_tokens=64)
            print(f"  {tier} -> {reply.strip()[:80]!r}  ({time.time() - t0:.1f}s)")
        print(f"  usage: {tf.usage}")

    backend = make_backend(args.backend)
    print(f"\n[2] Backend: {backend.name}")

    t0 = time.time()
    base = await backend.prepare_base()
    print(f"  base image: {base}  ({time.time() - t0:.1f}s)")

    print("\n[3] Network and uv inside the sandbox (pip install needs both)")
    r = await backend.run(base, "uv --version && python -c \"import urllib.request as u; "
                                "print(u.urlopen('https://pypi.org/simple/pip/').status)\"",
                          timeout=180)
    print(f"  exit={r.exit_code} cost={r.cost} out={r.stdout.strip()[:120]!r}")
    if not r.ok:
        print(f"  stderr: {r.stderr.strip()[-400:]!r}")

    print("\n[4] Fork: three children of one checkpoint, run at the same time")
    parent = await backend.run(base, "echo parent > /work/marker && cat /work/marker",
                               persist=True, timeout=120)
    if parent.image is None:
        print(f"  could not create a checkpoint: {parent.stderr[-300:] or parent.error}")
        await backend.close()
        return
    t0 = time.time()
    kids = await asyncio.gather(*[
        backend.run(parent.image, f"echo {label} >> /work/marker && cat /work/marker",
                    persist=True, timeout=120)
        for label in ("A", "B", "C")
    ])
    print(f"  parent={parent.image}  ({time.time() - t0:.1f}s for three forks)")
    ok = True
    for label, kid in zip("ABC", kids):
        got = kid.stdout.split()
        want = ["parent", label]
        print(f"   {label}: {kid.image}  ->  {got}")
        ok = ok and got == want
    print("  fork OK: each child saw the parent's state and none saw a sibling's"
          if ok else "  FORK MISMATCH: state leaked between branches")

    await backend.close()


if __name__ == "__main__":
    asyncio.run(main())
