"""The title and end cards, in the site's own paper, ink and dye green, set in its own faces.
Drawn at 4x and downsampled so the circle and the ring come out clean."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

A = Path("broll/_assets")
S = 4
W, H = 1920 * S, 1080 * S
PAPER, INK, MUTED, DYE = "#ECEDE8", "#1E1F1C", "#545850", "#94D44A"


def font(name, px):
    """A variable face at one weight: SourceSerif4-VF has axes (weight, optical size), Geologica-VF
    has (weight, cursive, sharpness, slant)."""
    family, weight = name.split("-")
    f = ImageFont.truetype(str(A / f"{family}-VF.ttf"), px * S)
    f.set_variation_by_axes([int(weight), 60] if family == "SourceSerif4" else [int(weight), 0, 0, 0])
    return f


def card(path, closing=False):
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    # The headshot: a square from the top of the frame (the hair starts at y=27 of 1500), kept
    # square, so nothing is cut off and nothing is stretched.
    src = Image.open(A / "headshot.jpg").convert("RGB").crop((0, 0, 1000, 1000))
    R = 150 * S
    src = src.resize((2 * R, 2 * R), Image.LANCZOS)
    mask = Image.new("L", (2 * R, 2 * R), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 2 * R - 1, 2 * R - 1), fill=255)
    cx = W // 2
    cy = (330 if closing else 390) * S
    ring = 9 * S
    d.ellipse((cx - R - ring, cy - R - ring, cx + R + ring, cy + R + ring), fill=DYE)
    im.paste(src, (cx - R, cy - R), mask)

    y = cy + R + 52 * S
    d.text((cx, y), "Floodplain", font=font("SourceSerif4-600", 108), fill=INK, anchor="mt")
    y += 150 * S
    d.rectangle((cx - 32 * S, y, cx + 32 * S, y + 5 * S), fill=DYE)
    y += 38 * S
    d.text((cx, y), "jonathansolvesproblems.com", font=font("Geologica-400", 36), fill=MUTED, anchor="mt")

    if closing:
        y += 110 * S
        d.text((cx, y), "Code, data and the live page", font=font("Geologica-400", 30), fill=MUTED, anchor="mt")
        y += 56 * S
        d.text((cx, y), "github.com/JonathanSolvesProblems/floodplain", font=font("Geologica-600", 40), fill=INK, anchor="mt")
        y += 64 * S
        d.text((cx, y), "jonathansolvesproblems.github.io/floodplain", font=font("Geologica-600", 40), fill=INK, anchor="mt")

    im = im.resize((1920, 1080), Image.LANCZOS)
    im.save(path, "PNG")
    print("wrote", path)


card(Path("broll/s00-title.png"))
card(Path("broll/s99-end.png"), closing=True)
