"""Collect everything needed for CapCut -> export/  (folder layout and file names: see layout.py)

The <slug>-capcut/ folder holds only media CapCut accepts; the .srt and the timeline sit beside it.
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import edit_user_draft as E  # noqa: E402
import layout as L  # noqa: E402

ROOT = L.ROOT
MOVE_VI = {"zoom_in": "zoom vào chậm", "zoom_out": "zoom ra chậm",
           "pan_left": "lia sang trái", "pan_right": "lia sang phải"}


def srt_time(t):
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s % 1) * 1000)):03d}"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    shots = json.loads((ROOT / "build/shots.json").read_text(encoding="utf-8"))
    missing = sorted({s["img"] for s in shots if not (ROOT / f"assets/img/{s['img']}.png").is_file()})
    if missing:
        sys.exit(f"images not generated yet: {missing}")

    if L.EXPORT.exists():
        shutil.rmtree(L.EXPORT)
    for sub in ("Anh", "Voice", "Nhac", "SFX"):
        (L.MEDIA / sub).mkdir(parents=True)

    words = E.merge_numbers(json.loads((ROOT / "build/words.json").read_text(encoding="utf-8")))
    caps = E.chunk(words)
    hits = [E.find(words, ph) + off for ph, _, off, kind in E.CUES if kind == "hit"]

    lines = ["SHOT  FILE                                         BAT DAU   DAI    HIEU UNG"]
    for i, s in enumerate(shots, 1):
        dst = L.image(i, s["img"])
        shutil.copy(ROOT / f"assets/img/{s['img']}.png", dst)
        dur = s["end"] - s["start"]
        hit = next((t for t in hits if s["start"] <= t < s["end"] - 0.3), None)
        move = f"punch-in giật nhanh ở giây {hit - s['start']:.1f} của shot" if hit else MOVE_VI[s["move"]]
        lines.append(f"{i:>4}  {dst.name:<45}{s['start']:>7.2f}s {dur:>5.2f}s  {move}")

    shutil.copy(ROOT / "assets/audio/vo.mp3", L.VOICE)
    if (ROOT / "assets/audio/music.mp3").is_file():
        shutil.copy(ROOT / "assets/audio/music.mp3", L.MUSIC)
    L.SRT.write_text("\n".join(
        f"{i}\n{srt_time(c['start'])} --> {srt_time(c['end'])}\n{' '.join(w for w, _ in c['parts'])}\n"
        for i, c in enumerate(caps, 1)), encoding="utf-8")

    sfx = []
    for a, b in zip(shots, shots[1:]):
        if a["img"] != b["img"]:
            sfx.append((b["start"] - 0.18, "whoosh-short.mp3", "đổi cảnh"))
    for ph, f, off, kind in E.CUES:
        t = E.find(words, ph) + off
        note = f'dồn tới "{ph}", chỉ lấy 2 giây cuối của file' if kind == "riser" else f'"{ph}"'
        sfx.append((t, f, note))
    for c in caps:
        if any(n for _, n in c["parts"]):
            sfx.append((c["start"], "pop.mp3", "hiện số: " + " ".join(w for w, _ in c["parts"])))
    for f in sorted({f for _, f, _ in sfx}):
        if (ROOT / "assets/sfx" / f).is_file():
            shutil.copy(ROOT / "assets/sfx" / f, L.sfx(f))

    rel = lambda p: p.relative_to(L.EXPORT).as_posix()
    lines += ["", f"VOICE:  {rel(L.VOICE)} đặt ở 0:00, volume 100%",
              f"NHAC:   {rel(L.MUSIC)} đặt ở 0:00, volume khoảng 6%, fade in 1.5s, fade out 3s",
              f"PHU DE: {rel(L.SRT)} ({len(caps)} dòng), CapCut: Text > Import captions",
              "", "SFX   (volume khoảng 30-40%, impact-bass để 15-20%)", "  GIAY   FILE                              GHI CHU"]
    lines += [f"{max(t, 0):>6.2f}s  {L.sfx(f).name:<33} {n}" for t, f, n in sorted(sfx)]
    L.TIMELINE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    n = sum(1 for p in L.MEDIA.rglob("*") if p.is_file())
    print(f"export -> {L.EXPORT}")
    print(f"  {L.MEDIA.name}/  {n} file media ({len(shots)} ảnh, voice, nhạc, {len({f for _, f, _ in sfx})} SFX)")
    print(f"  {L.SRT.name}  {len(caps)} dòng   |   {L.TIMELINE.name}")


if __name__ == "__main__":
    main()
