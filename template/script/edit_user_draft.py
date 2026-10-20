"""Build the CapCut timeline of a draft: zoomed/punched shots, short captions, voice, music, SFX.

  python script/edit_user_draft.py <draft-folder> --export     # use the files in export/ (normal case)
  python script/edit_user_draft.py <draft-folder> --dry-run    # write to build/dryrun/ only

Works on an empty draft (from create_project.py, or one the user made and dragged export/ into) or
on a draft that already has the photos on a track. Per-video settings live in script/video.json.
A full copy of the draft folder is saved to build/backup/ before anything is written.
CapCut must be closed.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from capcut import CAPCUT, SEG_DEFAULTS, aux, mat, uid  # noqa: E402
import layout as L  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
US = 1_000_000
FONT = ROOT / "assets/fonts/BeVietnamPro-Bold.ttf"

# ---- look ----
CAP_SIZE = 12.0
CAP_Y = -0.80
CAP_STROKE = 0.10
NUM_COLOR = [1.0, 0.85, 0.29]           # numbers in captions pop in warm yellow
MAX_WORDS, MAX_CHARS = 5, 26
ZOOM_LO, ZOOM_HI, PAN, PAN_SCALE = 1.02, 1.14, 0.045, 1.12
PUNCH_FROM, PUNCH_TO, PUNCH_IN = 1.04, 1.26, 0.22   # seconds to reach full punch

# ---- mix ----
MUSIC_VOL = 0.06                        # ~ -25 dB: music sits ~18 dB under the voice
MUSIC_FADE_IN, MUSIC_FADE_OUT = 1.5, 3.0
SFX_TARGET_LUFS = -22.0

# per-video settings, see video.json:
#   numbers: [[spoken phrase, on-screen text]]        longest first; shown in yellow
#   cues:    [[phrase in narration, sfx file, offset s, kind]]   kind: sfx | hit (also punches in) | riser
#   glue:    "word pair|word pair|..."                never split these across two captions
_CFG_FILE = ROOT / "script/video.json"
CFG = __import__("json").loads(_CFG_FILE.read_text(encoding="utf-8")) if _CFG_FILE.is_file() else {}
NUMBERS = [tuple(x) for x in CFG.get("numbers", [])]
CUES = [tuple(x) for x in CFG.get("cues", [])]
RISER_TAIL = 2.0                        # use only the last 2 s of the riser


def norm(w):
    return re.sub(r"[^\w]", "", unicodedata.normalize("NFC", w.lower()))


def lufs(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="ignore")
    m = re.findall(r"^\s+I:\s+(-?[\d.]+) LUFS", r.stderr, re.M)
    return float(m[-1]) if m else -20.0


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                        str(path)], capture_output=True, text=True)
    return float(r.stdout.strip())


# ---------------------------------------------------------------- words -> captions
def merge_numbers(words):
    toks = [norm(w["w"]) for w in words]
    out, i = [], 0
    while i < len(words):
        for phrase, digits in NUMBERS:
            p = phrase.split()
            if toks[i:i + len(p)] == p:
                last = words[i + len(p) - 1]
                tail = re.sub(r"^[\w]+", "", unicodedata.normalize("NFC", last["w"])) or ""
                first = words[i]["w"]
                d = digits[0].upper() + digits[1:] if first[:1].isupper() and not digits[0].isdigit() else digits
                out.append({"w": d + tail, "s": words[i]["s"], "e": last["e"],
                            "blk_end": last["blk_end"], "num": True})
                i += len(p)
                break
        else:
            out.append(dict(words[i]))
            i += 1
    return out


# word pairs that must never be split across two captions: common Vietnamese ones + video.json "glue"
_BASE_GLUE = """lịch sử|truyền thuyết|tương truyền|sử cũ|con trai|con gái|chị em|dấu tích|bằng chứng|khảo cổ|
việt nam|hà nội|người việt|xưng vương|đóng đô|khởi nghĩa|nghĩa quân|giao chiến|tử trận|thua trận|
mùa xuân|mùa hạ|mùa thu|mùa đông|năm sau|ngày sau|trước đó|bắt đầu|kết thúc|hoàn toàn|phần lớn|
dòng sông|bờ sông|lòng sông|cửa sông|cửa biển|mặt nước|ý định|xâm lược|quân đội|đem quân|kéo quân"""
GLUE = {tuple(x.split()) for x in (_BASE_GLUE + "|" + CFG.get("glue", "")).replace("\n", "").split("|")
        if " " in x.strip()}
# words that read badly as the last word of a caption
DANGLING = set("của và những một các là theo trong rằng thì để với bằng khi đã được sang từ cho nào đang "
               "không ở mà lên hơn rất quá chưa sẽ hề còn".split())


def clauses(words):
    out, cur = [], []
    for w in words:
        cur.append(w)
        if re.search(r"[,.:;!?]$", w["w"]):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    merged, carry = [], []
    for c in out:                                   # a one-word clause ("7 năm sau,") leads into the next
        c = carry + c
        carry = []
        if len(c) == 1:
            carry = c
            continue
        merged.append(c)
    if carry:
        merged[-1:] = [merged[-1] + carry] if merged else [carry]
    return merged


def split_clause(c):
    """Cut one clause into 2-5 word captions with the fewest bad breaks (dynamic programming)."""
    n = len(c)
    key = [norm(w["w"]) for w in c]
    chars = lambda j, i: len(" ".join(w["w"] for w in c[j:i]))

    def penalty(i):                                  # cost of breaking between c[i-1] and c[i]
        if i >= n:
            return 0.0
        p = 0.0
        if (key[i - 1], key[i]) in GLUE:
            p += 12
        if key[i - 1] in DANGLING:
            p += 5
        if c[i].get("num") and key[i - 1] in ("ngày", "năm", "tháng", "trưa", "lúc", "suốt"):
            p += 12
        return p

    best = [0.0] + [float("inf")] * n
    back = [0] * (n + 1)
    for i in range(1, n + 1):
        for j in range(max(0, i - MAX_WORDS), i):
            size = i - j
            if size < 2 and n > 1:
                continue
            if chars(j, i) > MAX_CHARS + 4 and size > 1:
                continue
            cost = best[j] + 0.6 * (size - 3.5) ** 2 + penalty(i)
            if cost < best[i]:
                best[i], back[i] = cost, j
    cuts, i = [], n
    while i > 0:
        cuts.append((back[i], i))
        i = back[i]
    return [c[j:i] for j, i in reversed(cuts)]


def sentences(words):
    """Split at the start of every vo.txt line (TTS may have turned a full stop into a comma)."""
    vo = ROOT / "script/vo.txt"
    if not vo.is_file():
        return [words]
    lines = [l.split() for l in vo.read_text(encoding="utf-8").splitlines() if l.strip()]
    toks = [norm(w["w"]) for w in words]
    cuts, pos = [0], 0
    for line in lines[1:]:
        head = [norm(t) for t in line[:3]]
        for i in range(pos + 1, len(toks) - 2):
            if toks[i:i + 3] == head:
                cuts.append(i)
                pos = i
                break
    cuts.append(len(words))
    return [words[a:b] for a, b in zip(cuts, cuts[1:]) if b > a]


def chunk(words):
    words = [dict(w, w=w["w"].lstrip(".…")) for w in words]
    chunks = [piece for sent in sentences(words) for cl in clauses(sent) for piece in split_clause(cl)]
    caps = []
    for c in chunks:
        parts = [(re.sub(r"[,.:;]+$", "", x["w"]) if j == len(c) - 1 else x["w"], x.get("num", False))
                 for j, x in enumerate(c)]
        caps.append({"start": c[0]["s"], "end": c[-1]["e"] + 0.25, "last_e": c[-1]["e"], "parts": parts})
    for a_, b_ in zip(caps, caps[1:]):               # monotonic, no overlaps, bridge short gaps
        b_["start"] = max(b_["start"], a_["start"] + 0.35)
        if b_["start"] - a_["last_e"] < 0.6:
            a_["end"] = b_["start"]
        a_["end"] = min(a_["end"], b_["start"])
    for i, c in enumerate(caps):
        end = max(c["end"], c["start"] + 0.4)
        if i + 1 < len(caps):
            end = min(end, caps[i + 1]["start"])
        c["start"], c["end"] = round(c["start"], 3), round(end, 3)
        del c["last_e"]
    return caps


def find(words, phrase):
    p = [norm(x) for x in phrase.split()]
    toks = [norm(w["w"]) for w in words]
    for i in range(len(toks) - len(p) + 1):
        if toks[i:i + len(p)] == p:
            return words[i]["s"]
    sys.exit(f"cue phrase not found in narration: '{phrase}'")


# ---------------------------------------------------------------- keyframes
def kf(t, v):
    return {"id": uid(), "time_offset": int(t), "values": [v], "curveType": "Line", "graphID": "",
            "left_control": {"x": 0.0, "y": 0.0}, "right_control": {"x": 0.0, "y": 0.0},
            "string_value": ""}


def channels(pts_scale, pts_x):
    def ch(prop, pts):
        return {"id": uid(), "material_id": "", "property_type": prop,
                "keyframe_list": [kf(t, v) for t, v in pts]}
    return [ch("KFTypeScaleX", pts_scale), ch("KFTypeScaleY", pts_scale),
            ch("KFTypePositionX", pts_x), ch("KFTypePositionY", [(p[0], 0.0) for p in pts_x])]


def motion(move, dur, hit=None):
    """-> (common_keyframes, start scale, start x). hit = seconds into the shot for a punch-in."""
    if hit is not None:
        h = int(hit * US)
        p = min(h + int(PUNCH_IN * US), dur)
        sc = [(0, PUNCH_FROM), (h, PUNCH_FROM), (p, PUNCH_TO), (dur, PUNCH_TO + 0.03)]
        return channels(sc, [(0, 0.0), (dur, 0.0)]), PUNCH_FROM, 0.0
    if move == "zoom_in":
        return channels([(0, ZOOM_LO), (dur, ZOOM_HI)], [(0, 0.0), (dur, 0.0)]), ZOOM_LO, 0.0
    if move == "zoom_out":
        return channels([(0, ZOOM_HI), (dur, ZOOM_LO)], [(0, 0.0), (dur, 0.0)]), ZOOM_HI, 0.0
    x0, x1 = (PAN, -PAN) if move == "pan_right" else (-PAN, PAN)
    return channels([(0, PAN_SCALE), (dur, PAN_SCALE)], [(0, x0), (dur, x1)]), PAN_SCALE, x0


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--export", action="store_true", help="point every file at export/ (what the user imported)")
    a = ap.parse_args()
    global ASSETS
    ASSETS = ROOT / "export"

    src = CAPCUT / a.folder
    if not a.dry_run and (src / ".locked").exists():
        sys.exit("CapCut still has this project open (.locked present). Close CapCut first.")

    doc = json.loads((src / "draft_content.json").read_text(encoding="utf-8"))
    base_audio, base_beat, base_fade, base_text = mat("audio"), mat("beat"), mat("audio_fade"), mat("text")
    mats = doc["materials"]
    by_id = {m["id"]: (k, m) for k, v in mats.items() if isinstance(v, list)
             for m in v if isinstance(m, dict) and "id" in m}

    # the user's own first image segment is the template; an empty timeline borrows one from draft 1007
    user_vtrack = next((t for t in doc["tracks"] if t["type"] == "video" and t["segments"]), None)
    if user_vtrack:
        seg_tpl = user_vtrack["segments"][0]
        aux_tpl = {by_id[r][0]: by_id[r][1] for r in seg_tpl["extra_material_refs"] if r in by_id}
    else:
        seg_tpl = mat("segment")
        aux_tpl = {k: aux(k) for k in ("speeds", "placeholder_infos", "canvases", "sound_channel_mappings",
                                       "material_colors", "vocal_separations")}
        user_vtrack = {"id": uid(), "type": "video", "flag": 0, "attribute": 0, "name": "",
                       "is_default_name": True, "segments": []}
        if a.export:                      # one photo material per numbered shot file the user imported
            base_photo = mat("photo")
            mats["videos"] = []
            for i, s in enumerate(json.loads((ROOT / "build/shots.json").read_text(encoding="utf-8")), 1):
                p = L.image(i, s["img"])
                m = deepcopy(base_photo)
                m.update(id=uid(), type="photo", path=str(p).replace("\\", "/"), material_name=p.name,
                         width=1920, height=1080, duration=10_800_000_000, has_audio=False,
                         unique_id="", local_id="", media_path="")
                mats["videos"].append(m)

    def new_aux(kinds):
        refs = []
        for k in kinds:
            d = deepcopy(aux_tpl.get(k) or (base_beat if k == "beats" else None))
            d["id"] = uid()
            mats.setdefault(k, []).append(d)
            refs.append(d["id"])
        return refs

    photo_for, photo_by_file = {}, {}
    for m in mats["videos"]:
        stem = Path(m["path"]).stem
        photo_for[re.sub(r"^\d+-", "", stem)] = m["id"]
        photo_by_file[Path(m["path"]).name] = m["id"]

    shots = json.loads((ROOT / "build/shots.json").read_text(encoding="utf-8"))
    for i, s in enumerate(shots, 1):          # prefer the numbered per-shot file when it exists
        s["mat"] = photo_by_file.get(L.image(i, s["img"]).name) or photo_for.get(s["img"])
    words = merge_numbers(json.loads((ROOT / "build/words.json").read_text(encoding="utf-8")))
    caps = chunk(words)
    if a.export:
        vo, music = L.VOICE, L.MUSIC
    else:
        vo, music = ROOT / "assets/audio/vo.mp3", ROOT / "assets/audio/music.mp3"
    vo_dur = duration(vo)

    cue_times = [(find(words, ph) + off, f, kind) for ph, f, off, kind in CUES]
    hits = [t for t, _, kind in cue_times if kind == "hit"]

    # ---- image track ----
    vsegs = []
    for s in shots:
        if not s["mat"]:
            sys.exit(f"no photo in project for '{s['img']}'")
        start, end = s["start"], s["end"]
        dur = int(round((end - start) * US))
        hit = next((t - start for t in hits if start <= t < end - 0.3), None)
        kfs, sc, x = motion(s["move"], dur, hit)
        seg = deepcopy(seg_tpl)
        seg.update(id=uid(), material_id=s["mat"],
                   source_timerange={"start": 0, "duration": dur},
                   target_timerange={"start": int(start * US), "duration": dur},
                   extra_material_refs=new_aux(list(aux_tpl.keys())),
                   common_keyframes=kfs, keyframe_refs=[])
        seg["clip"] = {**seg["clip"], "scale": {"x": sc, "y": sc}, "transform": {"x": x, "y": 0.0}}
        vsegs.append(seg)
    user_vtrack["segments"] = vsegs

    # ---- audio helpers ----
    def audio_mat(path, name):
        m = deepcopy(base_audio)
        m.update(id=uid(), name=name, path=str(path).replace("\\", "/"), duration=int(duration(path) * US),
                 type="extract_music", music_id="", category_id="", category_name="", resource_id="",
                 effect_id="", request_id="", app_id=0, wave_points=[])
        mats.setdefault("audios", []).append(m)
        return m

    def audio_seg(mat, start, src_start, dur, vol, fade=None, track_idx=1):
        refs = new_aux(["speeds", "placeholder_infos", "beats", "sound_channel_mappings", "vocal_separations"])
        if fade:
            f = deepcopy(base_fade)
            f.update(id=uid(), fade_in_duration=int(fade[0] * US), fade_out_duration=int(fade[1] * US))
            mats.setdefault("audio_fades", []).append(f)
            refs.append(f["id"])
        s = deepcopy(SEG_DEFAULTS)
        s.update(id=uid(), material_id=mat["id"],
                 source_timerange={"start": int(src_start * US), "duration": int(dur * US)},
                 target_timerange={"start": int(start * US), "duration": int(dur * US)},
                 extra_material_refs=refs, clip=None, uniform_scale=None, render_index=0,
                 track_render_index=track_idx, volume=vol, last_nonzero_volume=vol)
        return s

    def track(kind, segs, name=""):
        return {"id": uid(), "type": kind, "flag": 0, "attribute": 0, "name": name,
                "is_default_name": not name, "segments": segs}

    # ---- voiceover + music ----
    vo_m = audio_mat(vo, "vo.mp3")
    vo_track = track("audio", [audio_seg(vo_m, 0, 0, vo_dur, 1.0, track_idx=1)], "Voice")
    music_tracks = []
    if music.is_file():
        mu_m = audio_mat(music, "music.mp3")
        music_tracks = [track("audio", [audio_seg(mu_m, 0, 0, vo_dur + 1.0, MUSIC_VOL,
                                                  fade=(MUSIC_FADE_IN, MUSIC_FADE_OUT), track_idx=2)], "Music")]
    else:
        print(f"  no music file ({music.name}), music track skipped")

    # ---- SFX: whoosh on every change of picture, cues on story beats, pop on numbers ----
    events = []
    for a_, b_ in zip(shots, shots[1:]):
        if a_["img"] != b_["img"]:
            events.append((b_["start"] - 0.18, "whoosh-short.mp3", 0.0))
    for t, f, kind in cue_times:
        events.append((t, f, RISER_TAIL if kind == "riser" else 0.0))
    for c in caps:
        if any(n for _, n in c["parts"]):
            events.append((c["start"], "pop.mp3", 0.0))
    events.sort()

    sfx_mats, gain, lanes = {}, {}, []
    for t, f, tail in events:
        p = L.sfx(f) if a.export else ROOT / "assets/sfx" / f
        if not p.is_file():
            if f not in gain:
                print(f"  missing SFX {f}, skipped")
                gain[f] = None
            continue
        if f not in sfx_mats:
            sfx_mats[f] = audio_mat(p, f)
            gain[f] = min(1.0, 10 ** ((SFX_TARGET_LUFS - lufs(p)) / 20))
        full = duration(p)
        src0 = max(full - tail, 0.0) if tail else 0.0
        length = min(full - src0, vo_dur + 1.0 - max(t, 0))
        start = max(t, 0.0)
        for lane in lanes:                                  # first lane with room
            if lane[-1][0] + lane[-1][1] <= start:
                lane.append((start, length, f, src0))
                break
        else:
            lanes.append([(start, length, f, src0)])
    sfx_tracks = [track("audio", [audio_seg(sfx_mats[f], s, src0, ln, round(gain[f], 3), track_idx=3 + i)
                                  for s, ln, f, src0 in lane], f"SFX {i + 1}")
                  for i, lane in enumerate(lanes)]

    # ---- captions ----
    fp = str(FONT).replace("\\", "/")
    tsegs = []
    for c in caps:
        text, styles, pos = "", [], 0
        for j, (w, is_num) in enumerate(c["parts"]):
            piece = (" " if j else "") + w
            text += piece
            styles.append({
                "fill": {"alpha": 1.0, "content": {"render_type": "solid", "solid": {
                    "alpha": 1.0, "color": NUM_COLOR if is_num else [1.0, 1.0, 1.0]}}},
                "font": {"id": "", "path": fp}, "range": [pos, pos + len(piece)], "size": CAP_SIZE,
                "strokes": [{"alpha": 1.0, "content": {"render_type": "solid",
                                                       "solid": {"alpha": 1.0, "color": [0.0, 0.0, 0.0]}},
                             "width": CAP_STROKE}],
                "useLetterColor": True})
            pos += len(piece)
        tm = deepcopy(base_text)
        tm.update(id=uid(), font_path=fp, font_id="", font_resource_id="", font_name="", font_title="none",
                  font_url="", fonts=[], font_size=CAP_SIZE, text_color="#ffffff", border_color="#000000",
                  border_width=CAP_STROKE, border_alpha=1.0, border_mode=0, has_shadow=False, alignment=1,
                  line_max_width=0.9, base_content="", recognize_text="", words={}, current_words={},
                  subtitle_keywords=None, caption_template_info=None,
                  content=json.dumps({"text": text, "styles": styles}, ensure_ascii=False))
        mats.setdefault("texts", []).append(tm)
        s = deepcopy(SEG_DEFAULTS)
        s.update(id=uid(), material_id=tm["id"], source_timerange=None,
                 target_timerange={"start": int(c["start"] * US), "duration": int((c["end"] - c["start"]) * US)},
                 extra_material_refs=new_aux(["material_colors"]),
                 clip={"scale": {"x": 1.0, "y": 1.0}, "rotation": 0.0, "transform": {"x": 0.0, "y": CAP_Y},
                       "flip": {"vertical": False, "horizontal": False}, "alpha": 1.0},
                 render_index=14000, track_render_index=2)
        tsegs.append(s)

    doc["tracks"] = [user_vtrack, track("text", tsegs, "Captions"), vo_track] + music_tracks + sfx_tracks
    used = {r for t in doc["tracks"] for sg in t["segments"] for r in [sg["material_id"], *sg["extra_material_refs"]]}
    for k in ("videos", "audios", "texts", "speeds", "placeholder_infos", "canvases", "sound_channel_mappings",
              "material_colors", "vocal_separations", "beats", "audio_fades"):
        if isinstance(mats.get(k), list):
            mats[k] = [m for m in mats[k] if m.get("id") in used]
    total = int((vo_dur + 1.0) * US)
    doc["duration"] = total

    # ---- write ----
    stamp = time.strftime("%Y%m%d-%H%M%S")
    if a.dry_run:
        dst = ROOT / "build/dryrun"
        dst.mkdir(parents=True, exist_ok=True)
    else:
        bak = ROOT / f"build/backup/{a.folder}-{stamp}"
        shutil.copytree(src, bak)
        print(f"backup -> {bak}")
        dst = src
    body = json.dumps(doc, ensure_ascii=False)
    # CapCut 9.x opens Timelines/<main_timeline_id>/draft_content.json, not the root copy; an empty
    # timeline left there wins and gets copied over the root. Write every copy.
    targets = [dst / "draft_content.json"]
    if not a.dry_run:
        proj = dst / "Timelines/project.json"
        if proj.is_file():
            tid = json.loads(proj.read_text(encoding="utf-8")).get("main_timeline_id")
            if tid:
                targets.append(dst / "Timelines" / tid / "draft_content.json")
        targets += [t.with_name("draft_content.json.bak") for t in list(targets)]
    for t in targets:
        t.parent.mkdir(parents=True, exist_ok=True)
        t.write_text(body, encoding="utf-8")
    if not a.dry_run:
        meta_p = dst / "draft_meta_info.json"
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        meta["tm_duration"] = total
        meta_p.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        rp = CAPCUT / "root_meta_info.json"
        root = json.loads(rp.read_text(encoding="utf-8"))
        for e in root["all_draft_store"]:
            if e.get("draft_fold_path", "").rstrip("/").endswith("/" + a.folder):
                e["tm_duration"] = total
        rp.write_text(json.dumps(root, ensure_ascii=False), encoding="utf-8")

    (ROOT / "build/captions-short.json").write_text(json.dumps(
        [{"start": c["start"], "end": c["end"], "text": " ".join(w for w, _ in c["parts"])} for c in caps],
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{'DRY RUN ' if a.dry_run else ''}-> {dst / 'draft_content.json'}")
    print(f"  {len(vsegs)} shots ({len(hits)} punch-ins), {len(tsegs)} captions, "
          f"{sum(len(l) for l in lanes)} sfx on {len(lanes)} lanes, music vol {MUSIC_VOL}, {total / US:.2f}s")


if __name__ == "__main__":
    main()
