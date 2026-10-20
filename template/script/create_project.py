"""Create a brand-new CapCut project with export/<slug>-capcut/ already imported into its media pool.

  python script/create_project.py <project-name>

Afterwards build the timeline with:  python script/edit_user_draft.py ntt-2 --export
CapCut must be closed.
"""
import json
import shutil
import subprocess
import sys
import time
import uuid
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from capcut import CAPCUT, TEMPLATE, uid  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
import layout as L  # noqa: E402
EXPORT = L.MEDIA
PHOTO, AUDIO = {".png", ".jpg", ".jpeg"}, {".mp3", ".wav", ".m4a"}


def lid():
    return str(uuid.uuid4())


def audio_us(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    return int(float(r.stdout.strip()) * 1_000_000)


def main():
    name = sys.argv[1]
    dst = CAPCUT / name
    if dst.exists():
        sys.exit(f"{dst} already exists")
    if not CAPCUT.is_dir():
        sys.exit(f"CapCut draft folder not found: {CAPCUT}  (set CAPCUT_DRAFTS)")
    if sys.platform == "win32" and "capcut.exe" in subprocess.run(
            ["tasklist"], capture_output=True, text=True).stdout.lower():
        sys.exit("close CapCut first")

    for rel_path, text in TEMPLATE["files"].items():        # an empty draft, written from the template
        f = dst / rel_path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")

    now_s, now_us = int(time.time()), int(time.time() * 1_000_000)
    pool, folders, rel = [], [], []
    for k, sub in enumerate(sorted(d for d in EXPORT.iterdir() if d.is_dir())):
        files = sorted(f for f in sub.iterdir() if f.suffix.lower() in PHOTO | AUDIO)
        if not files:
            continue
        fid = lid()
        folders.append({"creation_time": now_s, "display_name": sub.name, "filter_type": 0, "id": fid,
                        "import_time": now_s, "import_time_us": now_us + k, "material_color_tag": "",
                        "sort_sub_type": 0, "sort_type": 0, "subdraft_filter_type": 0})
        rel.append({"child_id": fid, "parent_id": ""})
        for j, f in enumerate(files):
            photo = f.suffix.lower() in PHOTO
            dur = 5_000_000 if photo else audio_us(f)
            mid = lid()
            pool.append({"ai_group_type": "", "create_time": now_s, "duration": dur, "enter_from": 0,
                         "extra_info": f.name, "file_Path": str(f).replace("\\", "/"),
                         "height": 1080 if photo else 0, "width": 1920 if photo else 0, "id": mid,
                         "import_time": now_s, "import_time_ms": now_us + 100 * k + j, "item_source": 1,
                         "material_color_tag": "", "md5": "", "metetype": "photo" if photo else "music",
                         "roughcut_time_range": {"duration": -1 if photo else dur, "start": -1 if photo else 0},
                         "sub_time_range": {"duration": -1, "start": -1}, "type": 0})
            rel.append({"child_id": mid, "parent_id": fid})

    root_item = {"creation_time": 0, "display_name": "", "filter_type": 0, "id": "", "import_time": 0,
                 "import_time_us": 0, "material_color_tag": "", "sort_sub_type": 0, "sort_type": 0,
                 "subdraft_filter_type": 0}
    (dst / "draft_virtual_store.json").write_text(json.dumps({
        "draft_materials": [],
        "draft_virtual_store": [{"type": 0, "value": [root_item] + folders},
                                {"type": 1, "value": rel},
                                {"type": 2, "value": []}]}, ensure_ascii=False), encoding="utf-8")

    draft_id = uid()
    meta = json.loads((dst / "draft_meta_info.json").read_text(encoding="utf-8"))
    groups = {g["type"]: g for g in meta.get("draft_materials", [])}
    groups.setdefault(0, {"type": 0, "value": []})["value"] = pool
    meta.update(draft_id=draft_id, draft_name=name, draft_fold_path=str(dst).replace("\\", "/"),
                draft_root_path=str(CAPCUT).replace("\\", "/"), draft_materials=list(groups.values()),
                tm_draft_create=now_us, tm_draft_modified=now_us, tm_duration=0)
    (dst / "draft_meta_info.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

    content = json.loads((dst / "draft_content.json").read_text(encoding="utf-8"))
    content["id"] = uid()
    (dst / "draft_content.json").write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")

    rp = CAPCUT / "root_meta_info.json"
    root = json.loads(rp.read_text(encoding="utf-8")) if rp.is_file() else {
        "all_draft_store": [], "draft_ids": [], "root_path": CAPCUT.as_posix()}
    store = root.setdefault("all_draft_store", [])
    e = deepcopy(TEMPLATE["root_entry"])
    e.update(draft_id=draft_id, draft_name=name, draft_fold_path=str(dst).replace("\\", "/"),
             draft_json_file=str(dst / "draft_content.json").replace("\\", "/"),
             draft_cover=str(dst / "draft_cover.jpg").replace("\\", "/"),
             tm_draft_create=now_us, tm_draft_modified=now_us, tm_duration=0)
    store.insert(0, e)
    if isinstance(root.get("draft_ids"), list):
        root["draft_ids"].insert(0, draft_id)
    rp.write_text(json.dumps(root, ensure_ascii=False), encoding="utf-8")

    print(f"project '{name}' -> {dst}  ({len(pool)} media in {len(folders)} folders)")


if __name__ == "__main__":
    main()
