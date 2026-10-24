"""Record the site shots frame by frame: a real 1280x720 viewport at 1.5x device scale, so the
page lays out exactly as DEMO.md says to record it and each frame is 1920x1080. For every
frame the scroll position and the CSS animations are set from the clip time, then one
screenshot is taken, so the motion is smooth whatever the capture speed. Frames identical to
the previous one are reused, and ffmpeg assembles the clip at 25 fps.

    py scripts/video/capture_site.py             # every site shot
    py scripts/video/capture_site.py 04-hero     # just these
"""
import asyncio
import shutil
import subprocess
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright

SITE = "https://jonathansolvesproblems.github.io/floodplain/"
OUT = Path("broll")
FRAMES = OUT / "_frames"
FPS = 30
W, H, DPR = 1280, 720, 1.5

HELPERS = """
window.__jump = (sel, o) => {
  const el = document.querySelector(sel);
  if (!el) return false;
  el.scrollIntoView({block: 'start', behavior: 'instant'});
  window.scrollBy(0, -o);
  return true;
};
window.__setState = (y, tms) => {
  window.scrollTo(0, y);
  for (const a of document.getAnimations()) { a.pause(); a.currentTime = tms; }
  return window.scrollY;
};
true;
"""

# Steps: ("jump", selector, offset_px) before the clock starts; then ("hold", s) | ("glide", delta_px, s).
SHOTS = {
    "04-hero": [("hold", 3), ("glide", 50, 13)],
    "05-method": [("jump", "section.method", 40), ("hold", 1), ("glide", 150, 17), ("hold", 3)],
    "06-ledger": [("jump", "section[aria-labelledby='ledger-title']", 40), ("hold", 1), ("glide", 280, 9), ("hold", 1)],
    "07-prerelease": [("jump", "p.trace__after", 290), ("hold", 1), ("glide", 280, 19), ("hold", 2)],
    "08-llm-top": [("hold", 2), ("glide", 250, 6), ("hold", 2)],
    "09-llm-why": [("jump", "section[aria-labelledby='why-title']", 40), ("hold", 1), ("glide", 170, 9), ("hold", 1)],
    "10-llm-patch": [("jump", ".patch", 50), ("hold", 1), ("glide", 70, 12), ("hold", 1)],
    "11-agno-steps": [("jump", ".agent-steps", 30), ("hold", 1), ("glide", 680, 13), ("hold", 3)],
    "12-agno-rounds": [("jump", ".trials", 40), ("hold", 1), ("glide", 280, 8), ("hold", 1)],
    "13-llm-rounds": [("jump", ".trials", 40), ("hold", 1), ("glide", 320, 11), ("hold", 2)],
    "14-watch": [("jump", "section.watch", 60), ("hold", 1), ("glide", 70, 7), ("hold", 1)],
}
URLS = {"08-llm-top": SITE + "#/llm", "09-llm-why": SITE + "#/llm", "10-llm-patch": SITE + "#/llm",
        "13-llm-rounds": SITE + "#/llm", "11-agno-steps": SITE + "#/openinference-instrumentation-agno",
        "12-agno-rounds": SITE + "#/openinference-instrumentation-agno"}


def ease(t):
    return 2 * t * t if t < 0.5 else -1 + (4 - 2 * t) * t


def timeline(steps, y0):
    """Scroll position for every frame, from the steps after the jump."""
    ys, y = [], y0
    for step in steps:
        if step[0] == "jump":
            continue
        n = int(round(step[-1] * FPS))
        if step[0] == "hold":
            ys += [y] * n
        else:
            d = step[1]
            ys += [y + d * ease((i + 1) / n) for i in range(n)]
            y += d
    return ys


async def shoot(browser, sid, steps):
    t0 = time.time()
    fdir = FRAMES / sid
    if fdir.exists():
        shutil.rmtree(fdir)
    fdir.mkdir(parents=True)
    ctx = await browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=DPR, color_scheme="light")
    page = await ctx.new_page()
    await page.goto(URLS.get(sid, SITE), wait_until="load", timeout=45000)
    try:
        await page.evaluate("document.fonts.ready")
    except Exception:
        pass
    await asyncio.sleep(1.5)
    await page.evaluate(HELPERS)
    for step in steps:
        if step[0] == "jump":
            ok = await page.evaluate("([s, o]) => window.__jump(s, o)", [step[1], step[2]])
            if not ok:
                print(f"    selector not found: {step[1]}")
    await asyncio.sleep(0.3)
    y0 = await page.evaluate("window.scrollY")
    ys = timeline(steps, y0)
    entries, prev, shots = [], None, 0
    for i, y in enumerate(ys):
        t = i / FPS
        state = (round(y * DPR), min(t, 3.0))  # animations are done by 3 s; after that only the scroll matters
        if state == prev:
            entries[-1][1] += 1
            continue
        await page.evaluate("([y, t]) => window.__setState(y, t)", [y, t * 1000])
        path = fdir / f"f{i:05d}.png"
        await page.screenshot(path=str(path))
        entries.append([path, 1])
        prev, shots = state, shots + 1
    await ctx.close()
    lst = fdir / "list.txt"
    lst.write_text("".join(f"file '{p.name}'\nduration {n / FPS:.4f}\n" for p, n in entries)
                   + f"file '{entries[-1][0].name}'\n", encoding="utf-8")
    dest = OUT / f"{sid}.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-vf", f"fps={FPS},format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                    str(dest)], check=True)
    for ext in (".webm",):
        old = OUT / f"{sid}{ext}"
        if old.exists():
            old.unlink()
    print(f"  {sid}: {len(ys) / FPS:.1f}s, {shots} screenshots, {time.time() - t0:.0f}s wall")


async def main(ids):
    FRAMES.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        for sid in ids:
            await shoot(browser, sid, SHOTS[sid])
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or list(SHOTS)))
