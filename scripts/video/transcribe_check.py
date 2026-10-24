"""Transcribe the narration with faster-whisper small, word timestamps on, so the spoken span and
every number can be checked against DEMO.md before anything is captured."""
import json
import sys
import time

from faster_whisper import WhisperModel

src = sys.argv[1]
out = sys.argv[2]
t0 = time.time()
model = WhisperModel("small", device="cpu", compute_type="int8")
segments, info = model.transcribe(
    src, word_timestamps=True, beam_size=5, language="en",
    initial_prompt=("Floodplain. openai 3.0.0 swapped httpx for httpx2. Simon Willison's llm. Nebius Token "
                    "Factory Sandboxes. NVIDIA Nemotron 3 Nano, Nemotron 3 Ultra. PyPI wheel. "
                    "openinference-instrumentation-agno, vlmrun. GitHub Action. openai 3.37.0."))
segs = []
for s in segments:
    segs.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip(),
                 "words": [{"word": w.word, "start": round(w.start, 2), "end": round(w.end, 2),
                            "p": round(w.probability, 2)} for w in (s.words or [])]})
words = [w for s in segs for w in s["words"]]
res = {"duration": info.duration, "first_word": words[0]["start"] if words else None,
       "last_word": words[-1]["end"] if words else None, "segments": segs}
json.dump(res, open(out, "w", encoding="utf-8"), indent=1)
print(f"{len(segs)} segments, {len(words)} words, speech {res['first_word']}s to {res['last_word']}s "
      f"of {info.duration:.1f}s, took {time.time() - t0:.0f}s")
print(" ".join(w["word"].strip() for w in words))
