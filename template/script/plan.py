"""One picture per spoken sentence -> build/shots.json

Sentences come from build/words.json (word-level timing). Sentence k uses the k-th key of
script/scenes.json in sorted order, so scene keys like "07-kim-quy" name the files too.
A sentence longer than SPLIT seconds gets a second shot on the same picture with a different move.
Pictures are never reused across sentences.
"""
import json
import sys
sys.stdout.reconfigure(encoding="utf-8")
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPLIT = 6.5
MOVES = ["zoom_in", "pan_right", "zoom_out", "pan_left"]

words = json.loads((ROOT / "build/words.json").read_text(encoding="utf-8"))
KEYS = sorted(json.loads((ROOT / "script/scenes.json").read_text(encoding="utf-8")))
# One sentence per line of vo.txt. TTS may rewrite punctuation, so cut where each line's first
# three words appear (in order) rather than at full stops.
norm = lambda t: re.sub(r"[^\w]", "", t.lower())
lines = [l.split() for l in (ROOT / "script/vo.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
toks = [norm(w["w"]) for w in words]
cuts, pos = [0], 0
for line in lines[1:]:
    head = [norm(t) for t in line[:3]]
    for i in range(pos + 1, len(toks) - 2):
        if toks[i:i + 3] == head:
            cuts.append(i)
            pos = i
            break
    else:
        sys.exit(f"cannot find the start of line: {' '.join(line[:6])}")
cuts.append(len(words))
sents = [words[a:b] for a, b in zip(cuts, cuts[1:])]

end_all = words[-1]["blk_end"]
assert len(sents) == len(KEYS), f"{len(sents)} sentences but {len(KEYS)} scenes in scenes.json"
shots, mi = [], 0
for k, s in enumerate(sents):
    start = 0.0 if k == 0 else s[0]["s"]
    end = sents[k + 1][0]["s"] if k + 1 < len(sents) else end_all
    parts = 2 if end - start > SPLIT else 1
    for j in range(parts):
        a = start + (end - start) * j / parts
        b = start + (end - start) * (j + 1) / parts
        shots.append({"i": len(shots), "img": KEYS[k], "note": " ".join(x["w"] for x in s)[:60],
                      "start": round(a, 3), "end": round(b, 3), "move": MOVES[mi % len(MOVES)]})
        mi += 1

(ROOT / "build/shots.json").write_text(json.dumps(shots, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{len(sents)} sentences -> {len(shots)} shots, {end_all:.1f}s")
for s in shots:
    print(f"  {s['img']} {s['start']:6.2f}-{s['end']:6.2f} ({s['end'] - s['start']:4.1f}s) {s['note']}")
