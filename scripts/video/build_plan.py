"""Build demo.edit-plan.json: the beats from DEMO.md cut at the words where they start in the
final narration, each on the clip that shows what the words say, with the source of every
figure as a lower third. Captions come from the same transcript, with Whisper's mangled
tokens repaired (openai 3 .0 .0, PiPi, Nemotron3Nano)."""
import json
import subprocess
from pathlib import Path

T = json.load(open("broll/_transcript-final.json", encoding="utf-8"))
INTRO = 2.8
END_CARD = 3.0
AUDIO_LEN = 173.6
MEASURED = "Measured: data/openai-3.0.0"

# (tokens as Whisper wrote them, stripped) -> the words the captions should show
FIXES = [
    (["3", ".0", ".0"], ["3.0.0"]),
    (["3", ".37", ".0"], ["3.37.0"]),
    (["lm"], ["llm"]),
    (["LLM"], ["llm"]),
    (["LLM's"], ["llm's"]),
    (["PiPi"], ["PyPI"]),
    (["Nemotron3Nano"], ["Nemotron", "3", "Nano"]),
    (["Nemotron3"], ["Nemotron", "3"]),
    (["http"], ["HTTP"]),
    (["GitHub", "action"], ["GitHub", "Action"]),
    (["open", "AI"], ["openai"]),
    (["and", "issue"], ["an", "issue"]),
    (["rerun"], ["re-run"]),
    (["content", "addressed"], ["content-addressed"]),
    (["Openai's"], ["openai's"]),
    (["Openai"], ["openai"]),
    (["test", "had"], ["tests", "had"]),
    (["installs", "on"], ["installs", "of"]),
    (["1069"], ["1,069"]),
]

# (clip, the first words of the beat, in_point into the clip, lower third). The first beat starts
# at 0; each beat ends where the next begins.
BEATS = [
    ("00-openai-v300", None, 2.0, "Source: openai-python v3.0.0 release notes"),
    ("01-issue-1608", ["and", "6", "hours"], 2.0, "Source: simonw/llm #1608"),
    ("03-release-0321", ["and", "it", "took"], 2.0, "Source: simonw/llm 0.32.1"),
    ("02-pypi-history", ["and", "openai", "ships"], 1.5, "Source: PyPI release history"),
    ("04-hero", ["So", "I", "built"], 0.0, "jonathansolvesproblems.github.io/floodplain"),
    ("05-method", ["Each", "one", "has"], 0.0, "Three forks on Nebius Sandboxes"),
    ("06-ledger", ["I", "ran", "it"], 0.0, MEASURED),
    ("04-hero", ["Of", "the", "20"], 7.0, MEASURED),
    ("07-prerelease", ["Then", "I", "gave"], 0.0, MEASURED),
    ("08-llm-top", ["Here's", "llm"], 0.0, MEASURED),
    ("09-llm-why", ["Nemotron", "3", "Nano"], 0.0, "Nemotron 3 Nano reads the log"),
    ("10-llm-patch", ["then", "Nemotron", "writes"], 0.0, "Source: simonw/llm 0.32.1"),
    ("11-agno-steps", ["for", "the", "other", "2"], 0.0, "Nemotron 3 Ultra, native tool calling"),
    ("12-agno-rounds", ["It", "fixed", "both"], 0.0, MEASURED),
    ("13-llm-rounds", ["on", "llm", "it", "kept"], 0.0, ""),
    ("14-watch", ["and", "it", "keeps", "going"], 0.0, "Daily GitHub Action"),
    ("15-issue-1", ["its", "first", "was"], 2.0, "Source: floodplain issue #1"),
    ("16-issue-2", ["Everything", "lands"], 6.0, ""),
]


def key(tok):
    return tok["word"].strip().rstrip(",.?!")


def trailing(tok):
    w = tok["word"].strip()
    return w[len(w.rstrip(",.?!")):]


def fix_words(words):
    out, i = [], 0
    while i < len(words):
        for pat, rep in FIXES:
            if [key(t) for t in words[i:i + len(pat)]] == pat:
                span = words[i:i + len(pat)]
                t0, t1 = span[0]["start"], span[-1]["end"]
                total = sum(len(r) for r in rep)
                t = t0
                for j, r in enumerate(rep):
                    dt = (t1 - t0) * len(r) / total
                    out.append({"word": " " + r + (trailing(span[-1]) if j == len(rep) - 1 else ""),
                                "start": round(t, 3), "end": round(t + dt, 3)})
                    t += dt
                i += len(pat)
                break
        else:
            out.append({"word": words[i]["word"], "start": words[i]["start"], "end": words[i]["end"]})
            i += 1
    return out


segments = []
for s in T["segments"]:
    ws = fix_words(s["words"])
    segments.append({"text": "".join(w["word"] for w in ws).strip(), "start": s["start"], "end": s["end"], "words": ws})
tokens = [w for s in segments for w in s["words"]]
# Whisper stamps the first word at 0.0 when the file opens in near-silence; the voice starts at
# SPEECH_ONSET (the silence measured on the raw take, trimmed and sped up), so the caption must too.
SPEECH_ONSET = 0.31
if tokens and tokens[0]["start"] < SPEECH_ONSET:
    tokens[0]["start"] = SPEECH_ONSET
    segments[0]["start"] = max(segments[0]["start"], SPEECH_ONSET)
transcript = {"text": " ".join(s["text"] for s in segments), "duration": segments[-1]["end"], "segments": segments}


def find(anchor, after=0):
    for i in range(after, len(tokens) - len(anchor) + 1):
        if [key(t) for t in tokens[i:i + len(anchor)]] == anchor:
            return i
    raise SystemExit(f"anchor not found: {anchor}")


starts, pos = [], 0
for clip, anchor, _, _ in BEATS:
    if anchor is None:
        starts.append(0.0)
        continue
    pos = find(anchor, pos)
    starts.append(tokens[pos]["start"])

segs = []
for n, (clip, _, in_point, lower) in enumerate(BEATS):
    start = starts[n]
    end = starts[n + 1] if n + 1 < len(BEATS) else AUDIO_LEN
    segs.append({"clip_id": clip, "start_time": round(start, 3), "end_time": round(end, 3),
                 "lower_third": lower, "effect": "none", "in_point": in_point})
segs.append({"clip_id": "s99-end", "start_time": AUDIO_LEN, "end_time": AUDIO_LEN + END_CARD,
             "lower_third": "", "effect": "none"})


def clip_len(stem):
    for ext in (".webm", ".mp4", ".png"):
        p = Path("broll") / f"{stem}{ext}"
        if p.exists():
            if ext == ".png":
                return None
            return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                         "default=nw=1:nk=1", str(p)], capture_output=True, text=True).stdout)
    return -1


for s in segs:
    need = s["end_time"] - s["start_time"]
    have = clip_len(s["clip_id"])
    flag = ""
    if have == -1:
        flag = "  MISSING"
    elif have is not None and have - s.get("in_point", 0) < need:
        flag = f"  SHORT: clip {have:.1f}s, in {s.get('in_point', 0)}, needs {need:.1f}s"
    print(f"{s['start_time']:7.2f} {s['end_time']:7.2f} {need:5.1f}s  {s['clip_id']:<16} {s['lower_third']}{flag}")

plan = {"project_name": "Floodplain", "add_intro_card": True, "intro_clip": "s00-title", "intro_duration": INTRO,
        "intro_effect": "none", "add_outro_card": False, "theme": {"captions": {"margin_v": 90}},
        "segments": segs, "_transcript": transcript}
Path("demo.edit-plan.json").write_text(json.dumps(plan, indent=1), encoding="utf-8")
print("wrote demo.edit-plan.json;", len(tokens), "caption words; video ends at", round(INTRO + AUDIO_LEN + END_CARD, 1), "s")
print(transcript["text"])
