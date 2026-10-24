"""Rebuild the demo's audio track: 48 kHz, no digital silence anywhere, one clean mux.

Usage:
    py scripts/video/fix_audio.py demo.mp4 demo-final.mp4

vidkit's render leaves the intro delay as exact digital zeros, and this narration (recorded
through a noise gate) has exact zeros between phrases too. Some playback chains, YouTube in
Chrome among them, go idle on exact zeros and click when signal resumes. A -60 dB floor
under the title card fixed that but was audible as hiss on headphones.

So the floor here is far below hearing: dark noise (one-pole lowpass at 200 Hz, nothing
under 40 Hz) at FLOOR_DB RMS, added only where the programme is near-silent, with 50 ms
crossfades so it never switches on or off audibly. It exists only to keep every sample off
zero. The script checks the ENCODED file afterwards and fails if any 10 ms window decodes
to exact silence, because AAC can quantise a very quiet signal back to zero.
"""

from __future__ import annotations

import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

SR = 48000
FLOOR_DB = -84.0  # RMS; inaudible at any sane volume, still never exact zero after AAC
QUIET_DB = -70.0  # a 10 ms window quieter than this counts as a gap to be floored
PEAK_DB = -1.5    # sample-peak ceiling, so the true peak stays about -1 dBTP


def one_pole_lowpass(x: np.ndarray, hz: float) -> np.ndarray:
    a = np.exp(-2 * np.pi * hz / SR)
    from scipy.signal import lfilter  # noqa: PLC0415
    return lfilter([1 - a], [1, -a], x)


def one_pole_highpass(x: np.ndarray, hz: float) -> np.ndarray:
    b = np.exp(-2 * np.pi * hz / SR)
    from scipy.signal import lfilter  # noqa: PLC0415
    return lfilter([b, -b], [1, -b], x)


def build(src: str, fixed: Path) -> None:
    tmp = fixed.with_suffix(".decoded.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-vn", "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", str(tmp)], check=True)
    with wave.open(str(tmp)) as w:
        audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768
    tmp.unlink()

    n = len(audio)
    noise = np.random.default_rng(0).standard_normal(n)
    floor = one_pole_highpass(one_pole_lowpass(noise, 200), 40)
    floor *= 10 ** (FLOOR_DB / 20) / np.sqrt(np.mean(floor ** 2))

    # Gate: 1 where the programme is near-silent, smoothed with 50 ms ramps.
    win = SR // 100
    rms = np.sqrt(np.convolve(audio ** 2, np.ones(win) / win, mode="same"))
    gate = (rms < 10 ** (QUIET_DB / 20)).astype(np.float64)
    ramp = SR // 20
    gate = np.convolve(gate, np.ones(ramp) / ramp, mode="same")
    audio = audio + floor * gate

    # Keep the peak under the ceiling: loudnorm's dynamic mode does not always hold its true-peak
    # target, and AAC overshoots a little more. A sample peak of -1.5 dBFS leaves the true peak
    # near -1 dBTP on speech.
    peak = float(np.max(np.abs(audio))) if n else 0.0
    ceiling = 10 ** (PEAK_DB / 20)
    if peak > ceiling:
        audio *= ceiling / peak
        print(f"peak {20 * np.log10(peak):.1f} dBFS, scaled by {20 * np.log10(ceiling / peak):.1f} dB")

    # Write 24-bit-equivalent precision as 32-bit float so the floor is not rounded to zero.
    out = audio.astype(np.float32)
    raw = fixed.with_suffix(".f32")
    out.tofile(raw)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", str(raw), "-c:a", "pcm_f32le", str(fixed)], check=True)
    raw.unlink()


def silent_windows(path: str, start: float = 0.0, dur: float | None = None) -> int:
    cmd = ["ffmpeg", "-hide_banner", "-ss", str(start), "-i", path]
    if dur:
        cmd += ["-t", str(dur)]
    cmd += ["-af", "asetnsamples=480,astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.Peak_level", "-f", "null", "-"]
    out = subprocess.run(cmd, capture_output=True, text=True).stderr
    return out.count("Peak_level=-inf")


def main(src: str, dst: str) -> None:
    fixed = Path(dst).with_suffix(".fixed.wav")
    build(src, fixed)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-i", str(fixed), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-movflags", "+faststart", dst], check=True)
    fixed.unlink()
    zeros = silent_windows(dst)
    print(f"wrote {dst}; 10 ms windows of exact silence in the encoded file: {zeros}")
    if zeros > 2:  # the first window or two can be a fade-in edge
        sys.exit(f"{zeros} silent windows survived AAC: raise FLOOR_DB a few dB and re-run")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
