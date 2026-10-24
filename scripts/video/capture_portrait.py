"""Record the Short's b-roll at a phone viewport: 432x768 CSS px at 2.5x device scale, so every
frame is exactly 1080x1920 and the page uses its own phone layout (the river runs downward).
Frame by frame, like capture_site.py: the scroll position and animations are set from the
clip time, one screenshot each, assembled at 30 fps into broll/vertical/<id>.mp4.

Everything that must be read sits in the top 540 CSS px; the bottom 228 (570 device px)
belongs to the captions.

    py scripts/video/capture_portrait.py            # every shot
    py scripts/video/capture_portrait.py v04-hero   # just these
"""
import asyncio
import shutil
import subprocess
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright

SITE = "https://jonathansolvesproblems.github.io/floodplain/"
OUT = Path("broll/vertical")
FRAMES = Path("broll/_frames_v")
FPS = 30
W, H, DPR = 432, 768, 2.5
BAND = "drawbox=x=0:y=1350:w=1080:h=570:color=0x1E1F1C@1:t=fill,drawbox=x=0:y=1350:w=1080:h=6:color=0x94D44A@1:t=fill"

SET_STATE = """([y, tms]) => {
  window.scrollTo(0, y);
  for (const a of document.getAnimations()) { try { a.pause(); a.currentTime = tms; } catch (e) {} }
  return window.scrollY;
}"""

# url, then steps: ("y", px) sets the start, ("hold", s), ("to", px, s) glides there
SHOTS = {
    "v01-openai": ("https://github.com/openai/openai-python/releases/tag/v3.0.0",
                   [("y", 60), ("hold", 2), ("to", 200, 5)]),
    "v02-issue": ("https://github.com/simonw/llm/issues/1608", [("y", 40), ("hold", 2), ("to", 260, 8)]),
    "v03-release": ("https://github.com/simonw/llm/releases/tag/0.32.1", [("y", 60), ("hold", 1), ("to", 110, 4)]),
    "v04-hero": (SITE, [("y", 0), ("hold", 3), ("to", 210, 11)]),
    "v05-river": (SITE, [("y", 230), ("hold", 1), ("to", 250, 6)]),
    "v06-prerelease": (SITE, [("y", 1555), ("hold", 1), ("to", 1585, 18), ("hold", 2)]),
    "v07-patch": (SITE + "#/llm", [("y", 3440), ("hold", 1.5), ("to", 3585, 4), ("hold", 9)]),
}


def ease(t):
    return 2 * t * t if t < 0.5 else -1 + (4 - 2 * t) * t


def timeline(steps):
    ys, y = [], 0.0
    for step in steps:
        if step[0] == "y":
            y = float(step[1])
        elif step[0] == "hold":
            ys += [y] * int(round(step[1] * FPS))
        else:
            n, d = int(round(step[2] * FPS)), step[1] - y
            ys += [y + d * ease((i + 1) / n) for i in range(n)]
            y = float(step[1])
    return ys


async def shoot(browser, sid):
    url, steps = SHOTS[sid]
    t0 = time.time()
    fdir = FRAMES / sid
    if fdir.exists():
        shutil.rmtree(fdir)
    fdir.mkdir(parents=True)
    ctx = await browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=DPR,
                                    color_scheme="light", is_mobile=True, has_touch=True)
    page = await ctx.new_page()
    await page.goto(url, wait_until="load", timeout=45000)
    try:
        await page.evaluate("document.fonts.ready")
    except Exception:
        pass
    await asyncio.sleep(2.0)
    ys = timeline(steps)
    entries, prev = [], None
    for i, y in enumerate(ys):
        t = i / FPS
        state = (round(y * DPR), min(t, 3.0))
        if state == prev:
            entries[-1][1] += 1
            continue
        await page.evaluate(SET_STATE, [y, t * 1000])
        path = fdir / f"f{i:05d}.png"
        await page.screenshot(path=str(path))
        entries.append([path, 1])
        prev = state
    await ctx.close()
    lst = fdir / "list.txt"
    lst.write_text("".join(f"file '{p.name}'\nduration {n / FPS:.4f}\n" for p, n in entries)
                   + f"file '{entries[-1][0].name}'\n", encoding="utf-8")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    # the caption zone gets a band in the site's dark ink, so captions never sit on page text
                    "-vf", f"fps={FPS},scale=1080:1920,{BAND},format=yuv420p", "-c:v", "libx264", "-preset", "medium",
                    "-crf", "16", str(OUT / f"{sid}.mp4")], check=True)
    print(f"  {sid}: {len(ys) / FPS:.1f}s, {len(entries)} screenshots, {time.time() - t0:.0f}s wall")


async def main(ids):
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        for sid in ids:
            await shoot(browser, sid)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or list(SHOTS)))
