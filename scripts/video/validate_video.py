"""Checks on the rendered demo, not on the plan: length, sample rate, loudness, black frames,
exact silence at the head, AAC packet timing, and one frame from the middle of every beat so
each shot can be read against the words spoken over it."""
import json
import re
import subprocess
import sys
from pathlib import Path

video = sys.argv[1]
plan = json.load(open(sys.argv[2], encoding="utf-8"))
intro = float(plan.get("intro_duration", 0)) if plan.get("add_intro_card") else 0.0
out = Path("broll/_assets/check")
out.mkdir(parents=True, exist_ok=True)


def run(args):
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")


def probe(entries, stream=None):
    cmd = ["ffprobe", "-v", "error"]
    if stream:
        cmd += ["-select_streams", stream]
    cmd += ["-show_entries", entries, "-of", "default=nw=1", video]
    return run(cmd).stdout.strip()


print("== format")
print(probe("format=duration"))
print(probe("stream=codec_name,width,height,r_frame_rate", "v"))
print(probe("stream=codec_name,sample_rate,channels,start_time", "a"))

print("== loudness (integrated, true peak)")
err = run(["ffmpeg", "-hide_banner", "-i", video, "-af", "ebur128=peak=true", "-f", "null", "-"]).stderr
integrated = re.findall(r"^\s*I:\s+(-?[\d.]+) LUFS", err, re.M)
peak = re.findall(r"^\s*Peak:\s+(-?[\d.]+) dBFS", err, re.M)
print("I", integrated[-1] if integrated else "?", "LUFS; true peak", peak[-1] if peak else "?", "dBTP")

print("== black frames (expect none)")
err = run(["ffmpeg", "-hide_banner", "-i", video, "-vf", "blackdetect=d=0.3:pix_th=0.06", "-f", "null", "-"]).stderr
print([l for l in err.splitlines() if "black_start" in l] or "none")

print("== exact-silence 10 ms windows, first 6 s / last 6 s")
dur = float(probe("format=duration").split("=")[1])
for label, ss in (("head", 0), ("tail", max(0, dur - 6))):
    err = run(["ffmpeg", "-hide_banner", "-ss", str(ss), "-i", video, "-t", "6", "-af",
               "asetnsamples=480,astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.Peak_level",
               "-f", "null", "-"]).stderr
    print(label, err.count("Peak_level=-inf"))

print("== AAC packet durations (expect 1024s, one odd packet at the end)")
pk = run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "packet=duration", "-of", "csv=p=0", video]).stdout.split()
from collections import Counter
print(Counter(pk).most_common(4))

print("== one frame per beat")
for i, s in enumerate(plan["segments"]):
    mid = intro + (s["start_time"] + s["end_time"]) / 2
    p = out / f"{i:02d}-{s['clip_id']}.png"
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{mid:.2f}", "-i", video, "-frames:v", "1", "-vf", "scale=960:-1", str(p)])
    print(f"{i:02d} {mid:7.2f}s {s['clip_id']:<16} {s['lower_third']}")
