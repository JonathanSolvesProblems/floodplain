"""Build the YouTube Short from the long-form narration: five windows cut in measured silence,
joined with short breaths, a tail after the last word, a fresh transcript for the captions,
and a 1080x1920 edit plan whose first half second is the designed thumbnail card.

    py scripts/video/build_short.py

Reads broll/narration.wav and broll/_transcript-final.json; writes broll/short/narration.wav,
broll/short/_transcript.json and broll/short/short.edit-plan.json.
"""
import json
import subprocess
import wave
from pathlib import Path

import numpy as np

SRC = Path("broll/narration.wav")
OUT = Path("broll/short")
SR = 48000
GAP, TAIL, SILENT_DB = 0.4, 1.5, -55.0
CARD = 0.5

# (first words, last words) of each window, as Whisper wrote them in the long-form transcript
WINDOWS = [
    (["On", "the", "12th"], ["ship", "a", "fix."]),
    (["So", "I", "built"], ["Factory", "Sandboxes."]),
    (["Of", "the", "20"], ["3", "broke,"]),
    (["Then", "I", "gave"], ["before", "publishing."]),
    (["then", "Nemotron", "writes"], ["9", "days", "later,"]),
]

# clip, first words of the beat in the Short's own transcript (after FIXES)
BEATS = [
    ("v01-openai", None),
    ("v02-issue", ["hours", "later"]),
    ("v03-release", ["and", "it", "took"]),
    ("v04-hero", ["So", "I", "built"]),
    ("v05-river", ["Of", "the", "20"]),
    ("v06-prerelease", ["Then", "I", "gave"]),
    ("v07-patch", ["then", "Nemotron", "writes"]),
]

FIXES = [
    (["3", ".0", ".0"], ["3.0.0"]), (["lm"], ["llm"]), (["LLM"], ["llm"]), (["LLM's"], ["llm's"]),
    (["PiPi"], ["PyPI"]), (["http"], ["HTTP"]), (["Openai's"], ["openai's"]), (["Openai"], ["openai"]),
    (["installs", "on"], ["installs", "of"]), (["Nemotron3"], ["Nemotron", "3"]),
    (["broken", "test"], ["broken", "tests"]), (["pin", "Simon"], ["pin", "Simon"]),
    (["six"], ["6"]), (["nine"], ["9"]), (["three"], ["3"]),
    (["suites", "the", "release", "actually", "reached", "3", "broke"],
     ["suites", "the", "release", "actually", "reached,", "3", "broke"]),
]


def key(tok):
    return tok["word"].strip().rstrip(",.?!")


def find(tokens, words, after=0):
    """Index of the first run of tokens matching words, ignoring case and trailing punctuation."""
    words = [w.rstrip(",.?!").lower() for w in words]
    for i in range(after, len(tokens) - len(words) + 1):
        if [key(t).lower() for t in tokens[i:i + len(words)]] == words:
            return i
    raise SystemExit(f"not found: {words}")


def read_wav(p):
    with wave.open(str(p)) as w:
        assert w.getframerate() == SR and w.getnchannels() == 1
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768


def rms_db(x, t0, t1):
    seg = x[max(0, int(t0 * SR)):int(t1 * SR)]
    return -120.0 if len(seg) == 0 else 20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-9)


def quiet(x, t):
    return rms_db(x, t, t + 0.05) < SILENT_DB


def cut_start(x, t):
    """The latest silent 20 ms window in the 300 ms before the first word's onset, or, when the
    previous word runs straight into this one, the quietest point there. Never earlier: walking
    back to the last real silence can swallow the end of the previous sentence."""
    cands = [t - 0.3 + i * 0.005 for i in range(int(0.35 / 0.005))]
    levels = [(c, rms_db(x, c, c + 0.02)) for c in cands if c >= 0]
    silent = [c for c, db in levels if db < SILENT_DB]  # Whisper's onset can sit a hair early
    return max(silent) if silent else min(levels, key=lambda cl: cl[1])[0]


def cut_end(x, t):
    """Walk forward from the last word's onset until 100 ms of silence (the word has decayed)."""
    while t < len(x) / SR and not (quiet(x, t) and quiet(x, t + 0.05)):
        t += 0.01
    return t + 0.03


def fix_words(words):
    out, i = [], 0
    while i < len(words):
        for pat, rep in FIXES:
            if [key(t) for t in words[i:i + len(pat)]] == pat:
                span = words[i:i + len(pat)]
                t0, t1 = span[0]["start"], span[-1]["end"]
                tail = span[-1]["word"].strip()[len(span[-1]["word"].strip().rstrip(",.?!")):]
                total, t = sum(len(r) for r in rep), t0
                for j, r in enumerate(rep):
                    dt = (t1 - t0) * len(r) / total
                    out.append({"word": " " + r + (tail if j == len(rep) - 1 else ""),
                                "start": round(t, 3), "end": round(t + dt, 3)})
                    t += dt
                i += len(pat)
                break
        else:
            out.append({k: words[i][k] for k in ("word", "start", "end")})
            i += 1
    return out


OUT.mkdir(parents=True, exist_ok=True)
audio = read_wav(SRC)
src_tokens = [w for s in json.load(open("broll/_transcript-final.json", encoding="utf-8"))["segments"] for w in s["words"]]

pieces, pos = [], 0
for first, last in WINDOWS:
    a = find(src_tokens, first, pos)
    b = find(src_tokens, last, a) + len(last) - 1
    pos = b
    t0, t1 = cut_start(audio, src_tokens[a]["start"]), cut_end(audio, src_tokens[b]["start"])
    pieces.append(audio[int(t0 * SR):int(t1 * SR)])
    print(f"window {t0:7.2f} {t1:7.2f}  {t1 - t0:5.2f}s  {' '.join(first)} ... {' '.join(last)}")

gap = np.zeros(int(GAP * SR), dtype=np.float32)
fade = int(0.03 * SR)
for p in pieces:  # round both edges, in silence, so no join can click
    p[:fade] *= np.linspace(0, 1, fade)
    p[-fade:] *= np.linspace(1, 0, fade)
joined = np.concatenate([x for p in pieces for x in (p, gap)][:-1] + [np.zeros(int(TAIL * SR), dtype=np.float32)])
out_wav = OUT / "narration.wav"
with wave.open(str(out_wav), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((np.clip(joined, -1, 1) * 32767).astype(np.int16).tobytes())
duration = len(joined) / SR
print(f"short narration {duration:.2f}s")

subprocess.run(["py", "scripts/video/transcribe_check.py", str(out_wav), str(OUT / "_transcript.json")], check=True)
T = json.load(open(OUT / "_transcript.json", encoding="utf-8"))
segments = []
for s in T["segments"]:
    ws = fix_words(s["words"])
    segments.append({"text": "".join(w["word"] for w in ws).strip(), "start": s["start"], "end": s["end"], "words": ws})
tokens = [w for s in segments for w in s["words"]]
# The card is the Shorts-shelf thumbnail, picked from frame 0, so no caption may be drawn on it:
# the first words appear when the card ends, though the voice starts under it.
for w in tokens:
    if w["start"] < CARD:
        w["start"], w["end"] = CARD, max(w["end"], CARD + 0.05)
segments[0]["start"] = max(segments[0]["start"], CARD)
transcript = {"text": " ".join(s["text"] for s in segments), "duration": segments[-1]["end"], "segments": segments}

starts, p = [], 0
for clip, anchor in BEATS:
    if anchor is None:
        starts.append(CARD)
        continue
    p = find(tokens, anchor, p)
    starts.append(tokens[p]["start"])
segs = [{"clip_id": "s00", "start_time": 0.0, "end_time": CARD, "lower_third": "", "effect": "none"}]
for n, (clip, _) in enumerate(BEATS):
    end = starts[n + 1] if n + 1 < len(BEATS) else round(duration, 3)
    segs.append({"clip_id": clip, "start_time": round(starts[n], 3), "end_time": round(end, 3),
                 "lower_third": "", "effect": "none"})
for s in segs:
    print(f"{s['start_time']:7.2f} {s['end_time']:7.2f} {s['end_time'] - s['start_time']:5.1f}s  {s['clip_id']}")

plan = {"project_name": "Floodplain", "add_intro_card": False, "add_outro_card": False,
        "width": 1080, "height": 1920,
        "theme": {"captions": {"active": "FFE500", "word_pop": False, "margin_v": 250, "words_per_line": 4, "size": 76}},
        "segments": segs, "_transcript": transcript}
(OUT / "short.edit-plan.json").write_text(json.dumps(plan, indent=1), encoding="utf-8")
print("wrote", OUT / "short.edit-plan.json")
print(transcript["text"])
