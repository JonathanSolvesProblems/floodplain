"""The Devpost gallery: eight images at 3:2 in the demo video's order, one caption each, 140
characters at most. Rendered from the live page and the GitHub pages it cites, at a 1500x1000
viewport and 1.5x device scale, light theme as the page defaults to.

Output: broll/gallery/N-name.png plus broll/gallery/captions.md, one fenced block per image
holding the caption and nothing else. The character count is asserted here and printed to the
terminal only, never beside a caption, because a count beside a caption gets pasted with it.

    py scripts/video/gallery.py
"""
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "broll" / "gallery"
SITE = "https://jonathansolvesproblems.github.io/floodplain/"
W, H, DPR = 1500, 1000, 1.5

# name, url, selector scrolled to the top (None: top of page), offset in CSS px above it
SHOTS = [
    ("1-river", SITE, None, 0),
    ("2-the-break", "https://github.com/simonw/llm/issues/1608", None, 0),
    ("3-three-forks", SITE, "#method-title", 56),
    ("4-before-release", SITE, "p.trace__after", 330),
    ("5-why-it-broke", SITE + "#/llm", "section[aria-labelledby='why-title']", 30),
    ("6-same-pin", SITE + "#/llm", ".patch", 140),
    ("7-agent-steps", SITE + "#/openinference-instrumentation-agno", ".agent-steps", 12),
    ("8-still-watching", "https://github.com/JonathanSolvesProblems/floodplain/issues/1", None, 0),
]

CAPTIONS = {
    "1-river": "Run before openai 3.0.0 shipped, Floodplain found the 3 of 20 working test suites it broke, each forked three ways on Nebius Sandboxes.",
    "2-the-break": "The problem: openai 3.0.0 broke fresh installs of Simon Willison's llm. A user reported it 6 hours later. The fix took 9 days.",
    "3-three-forks": "Each dependent runs its own test suite in three forks of one checkout: before, the same again to catch flaky tests, and after.",
    "4-before-release": "Given OpenAI's own wheel before it was uploaded, all 31 working suites gave the same verdict as the real release, same tests broken.",
    "5-why-it-broke": "NVIDIA Nemotron 3 Nano explains why llm broke. The line it cites is checked word for word against the real log.",
    "6-same-pin": "Nemotron's patch passed llm's own test suite in a further fork. It is the same pin its maintainer shipped nine days later.",
    "7-agent-steps": "A Nemotron 3 Ultra agent chooses each step from what the last returned, then submits. Its patch passes in a fresh sandbox.",
    "8-still-watching": "It keeps watching: its daily check found openai 3.37.0 broke none of 21 working suites, and set aside a flaky test.",
}

for k, c in CAPTIONS.items():
    assert len(c) <= 140, f"{k}: {len(c)} characters, limit is 140"
assert [n for n, *_ in SHOTS] == list(CAPTIONS), "SHOTS and CAPTIONS must list the same names in the same order"
assert len(SHOTS) <= 8

OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    for name, url, sel, off in SHOTS:
        ctx = b.new_context(viewport={"width": W, "height": H}, device_scale_factor=DPR, color_scheme="light")
        pg = ctx.new_page()
        pg.goto(url, wait_until="load", timeout=60_000)
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(2500)  # the river's arrival animation, GitHub's late layout
        if sel:
            found = pg.evaluate(
                "([s, o]) => { const el = document.querySelector(s); if (!el) return false;"
                " window.scrollTo(0, el.getBoundingClientRect().top + window.scrollY - o); return true; }", [sel, off])
            assert found, f"{name}: selector not found: {sel}"
        pg.wait_for_timeout(800)
        pg.screenshot(path=str(OUT / f"{name}.png"))
        ctx.close()
    b.close()

lines = ["# Image gallery, upload in this order", "", "One caption per image. Copy the block contents only.", ""]
for name, *_ in SHOTS:
    lines += [f"## {name}.png", "", "```", CAPTIONS[name], "```", ""]
(OUT / "captions.md").write_text("\n".join(lines), encoding="utf-8")

for name, *_ in SHOTS:
    f = OUT / f"{name}.png"
    im = Image.open(f)
    ok = "ok " if abs(im.width / im.height - 1.5) < 0.01 and f.stat().st_size < 5_000_000 else "BAD"
    print(f"  {ok} {f.name:<24} {im.width}x{im.height}  {f.stat().st_size // 1024:>5} KB   caption {len(CAPTIONS[name]):>3}/140")

sheet = Image.new("RGB", (960 * 2, 640 * 4), "black")
for i, (name, *_) in enumerate(SHOTS):
    im = Image.open(OUT / f"{name}.png").convert("RGB").resize((956, 637), Image.LANCZOS)
    sheet.paste(im, ((i % 2) * 960 + 2, (i // 2) * 640 + 1))
sheet.save(OUT.parent / "_assets" / "gallery-sheet.png")
print(f"\n{len(SHOTS)} images + captions.md in {OUT.relative_to(ROOT)}")
