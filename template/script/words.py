"""Word-level timing for the voiceover -> build/words.json

Whisper gives timing but mishears Vietnamese tones, vivibe's SRT gives the exact words but only
per sentence. Align the two: SRT words are displayed, Whisper supplies the clock.
"""
import difflib
import json
import re
import unicodedata
from pathlib import Path

from faster_whisper import WhisperModel

ROOT = Path(__file__).resolve().parent.parent
WAV = ROOT / "assets/audio/vo.wav"
SRT = ROOT / "assets/audio/vo.srt"
OUT = ROOT / "build/words.json"


def norm(w):
    w = unicodedata.normalize("NFC", w.lower())
    return re.sub(r"[^\w]", "", w)


def ts(s):
    h, m, rest = s.split(":")
    sec, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms) / 1000


def srt_blocks():
    out = []
    for blk in re.split(r"\n\s*\n", SRT.read_text(encoding="utf-8").strip()):
        lines = [l for l in blk.splitlines() if l.strip()]
        a, b = lines[1].split(" --> ")
        out.append((ts(a), ts(b), " ".join(lines[2:])))
    return out


model = WhisperModel("small", device="cpu", compute_type="int8")
segs, _ = model.transcribe(str(WAV), language="vi", word_timestamps=True, vad_filter=False)
heard = [(w.start, w.end, w.word.strip()) for s in segs for w in s.words if w.word.strip()]
print(f"whisper: {len(heard)} words")

words = []
for b0, b1, text in srt_blocks():
    shown = text.split()
    hw = [h for h in heard if h[0] >= b0 - 0.25 and h[1] <= b1 + 0.25]
    times = [None] * len(shown)
    sm = difflib.SequenceMatcher(a=[norm(w) for w in shown], b=[norm(h[2]) for h in hw], autojunk=False)
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            times[blk.a + k] = (hw[blk.b + k][0], hw[blk.b + k][1])
    # anchor the block edges, then interpolate every gap linearly by position
    if times[0] is None:
        times[0] = (b0, b0)
    if times[-1] is None:
        times[-1] = (b1, b1)
    known = [i for i, t in enumerate(times) if t]
    for a, c in zip(known, known[1:]):
        for i in range(a + 1, c):
            f = (i - a) / (c - a)
            t = times[a][1] + f * (times[c][0] - times[a][1])
            times[i] = (t, t)
    matched = sum(1 for k in sm.get_matching_blocks() for _ in range(k.size))
    print(f"  block {b0:6.2f}-{b1:6.2f}: {len(shown):3d} words, {matched:3d} matched")
    for w, (s, e) in zip(shown, times):
        words.append({"w": w, "s": round(max(s, b0), 3), "e": round(min(max(e, s), b1), 3), "blk_end": b1})

OUT.write_text(json.dumps(words, ensure_ascii=False, indent=0), encoding="utf-8")
print(f"{len(words)} words -> {OUT}")
