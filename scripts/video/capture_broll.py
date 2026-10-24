"""Record the demo's b-roll: the live site and the GitHub and PyPI pages the narration cites,
one 1920x1080 webm per shot in broll/. Playwright records at the viewport's CSS size, so the
viewport is 1920x1080 and the page is zoomed 1.5x: it lays out as it does at 1280 wide, the
width DEMO.md says to record at, and the video is still full HD.

    py scripts/video/capture_broll.py            # every shot
    py scripts/video/capture_broll.py 04-hero    # just these
"""
import asyncio
import shutil
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright

SITE = "https://jonathansolvesproblems.github.io/floodplain/"
REPO = "https://github.com/JonathanSolvesProblems/floodplain"
OUT = Path("broll")
VID = OUT / "_videos"
W, H, ZOOM = 1920, 1080, 1.5

SETUP = """
document.documentElement.style.zoom = '%s';
window.__glide = (y, ms) => new Promise((res) => {
  const y0 = window.scrollY, d = y - y0, t0 = performance.now();
  const ease = (t) => (t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t);
  const step = (now) => {
    const t = Math.min(1, (now - t0) / ms);
    window.scrollTo(0, y0 + d * ease(t));
    if (t < 1) requestAnimationFrame(step); else res();
  };
  requestAnimationFrame(step);
});
window.__jump = (sel, o) => {
  const el = document.querySelector(sel);
  if (!el) return false;
  el.scrollIntoView({block: 'start', behavior: 'instant'});
  window.scrollBy(0, -o);
  return true;
};
""" % ZOOM

# Steps: ("go", url) | ("hold", seconds) | ("jump", selector, offset_px)
#        | ("glide", delta_px, ms)
SHOTS = {
    "00-openai-v300": [("go", "https://github.com/openai/openai-python/releases/tag/v3.0.0"), ("hold", 2.5),
                       ("glide", 420, 5000), ("hold", 3)],
    "01-issue-1608": [("go", "https://github.com/simonw/llm/issues/1608"), ("hold", 2.5),
                      ("glide", 420, 5000), ("hold", 3)],
    "02-pypi-history": [("go", "https://pypi.org/project/openai/#history"), ("hold", 2),
                        ("glide", 600, 6000), ("hold", 2)],
    "03-release-0321": [("go", "https://github.com/simonw/llm/releases/tag/0.32.1"), ("hold", 3),
                        ("glide", 160, 5000), ("hold", 3)],
    "04-hero": [("go", SITE), ("hold", 14)],
    "05-method": [("go", SITE), ("jump", "section.method", 60), ("hold", 1),
                  ("glide", 220, 17000), ("hold", 3)],
    "06-ledger": [("go", SITE), ("jump", "section[aria-labelledby='ledger-title']", 60), ("hold", 1),
                  ("glide", 420, 9000), ("hold", 1)],
    "07-prerelease": [("go", SITE), ("jump", "p.trace__after", 430), ("hold", 1),
                      ("glide", 400, 19000), ("hold", 3)],
    "08-llm-top": [("go", SITE + "#/llm"), ("hold", 3), ("glide", 380, 6000), ("hold", 3)],
    "09-llm-why": [("go", SITE + "#/llm"), ("jump", "section[aria-labelledby='why-title']", 60),
                   ("hold", 1), ("glide", 260, 9000), ("hold", 1)],
    "10-llm-patch": [("go", SITE + "#/llm"), ("jump", ".patch", 70), ("hold", 1),
                     ("glide", 100, 12000), ("hold", 1)],
    "11-agno-steps": [("go", SITE + "#/openinference-instrumentation-agno"), ("jump", ".agent-steps", 40),
                      ("hold", 1), ("glide", 1000, 12000), ("hold", 3)],
    "12-agno-rounds": [("go", SITE + "#/openinference-instrumentation-agno"), ("jump", ".trials", 60),
                       ("hold", 1), ("glide", 420, 8000), ("hold", 2)],
    "13-llm-rounds": [("go", SITE + "#/llm"), ("jump", ".trials", 60), ("hold", 1),
                      ("glide", 480, 10000), ("hold", 2)],
    "14-watch": [("go", SITE), ("jump", "section.watch", 90), ("hold", 2),
                 ("glide", 100, 6000), ("hold", 1)],
    "15-issue-1": [("go", REPO + "/issues/1"), ("hold", 2.5), ("glide", 500, 6000), ("hold", 2.5)],
    "16-issue-2": [("go", REPO + "/issues/2"), ("hold", 2), ("glide", 1300, 9000), ("hold", 3),
                   ("glide", 1400, 9000), ("hold", 4)],
}


async def run_steps(page, steps):
    for step in steps:
        kind = step[0]
        if kind == "go":
            await page.goto(step[1], wait_until="load", timeout=45000)
            await page.evaluate(SETUP)
            try:
                await page.evaluate("document.fonts.ready")
            except Exception:
                pass
            await asyncio.sleep(1.5)
        elif kind == "hold":
            await asyncio.sleep(step[1])
        elif kind == "jump":
            ok = await page.evaluate("([s, o]) => window.__jump(s, o)", [step[1], step[2]])
            if not ok:
                print(f"    selector not found: {step[1]}")
            await asyncio.sleep(0.3)
        elif kind == "glide":
            await page.evaluate("([d, ms]) => window.__glide(window.scrollY + d, ms)", [step[1], step[2]])


async def main(ids):
    OUT.mkdir(exist_ok=True)
    VID.mkdir(exist_ok=True)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        for sid in ids:
            steps = SHOTS[sid]
            t0 = time.time()
            ctx = await browser.new_context(viewport={"width": W, "height": H}, color_scheme="light",
                                            record_video_dir=str(VID),
                                            record_video_size={"width": W, "height": H})
            page = await ctx.new_page()
            try:
                await run_steps(page, steps)
            except Exception as e:
                print(f"  {sid}: step failed: {e}")
            await ctx.close()
            vids = sorted(VID.glob("*.webm"), key=lambda p: p.stat().st_mtime, reverse=True)
            if not vids:
                print(f"  {sid}: no video written")
                continue
            dest = OUT / f"{sid}.webm"
            shutil.move(str(vids[0]), str(dest))
            print(f"  {sid}: {dest.name} ({time.time() - t0:.0f}s wall)")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or list(SHOTS)))
