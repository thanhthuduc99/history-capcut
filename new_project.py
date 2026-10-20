"""Start a new history video project from the skill template.

  python .claude/skills/history-capcut/new_project.py <slug> --style dong-son [--dir lich-su-vn]

Creates <dir>/<slug>-long/ with:
  script/       all pipeline scripts + capcut_template.json
  script/style.txt   copied from template/style/<style>.txt (edit PERIOD / characters / NATURE)
  script/vo.txt, scenes.json, video.json   empty stubs to fill
  sources.md    stub to fill with checked facts
  assets/style-ref/anchor-E.jpg, assets/fonts/BeVietnamPro-Bold.ttf, assets/sfx/, assets/audio/music.mp3
  .env          copied from the repo root .env (VIVIBE_API_KEY, VIVIBE_VOICE)

Optional environment variables (or lines in the repo root .env):
  HC_MUSIC_FILE  background music to copy in (skipped if unset)
  HC_SFX_DIR     folder with whoosh-short.mp3, whoosh-cinematic.mp3, pop.mp3, riser.mp3,
                 impact-bass-1.mp3, impact-bass-2.mp3, sparkle.mp3 (skipped if unset)
"""
import argparse
import json
import os
import shutil
import sys
import urllib.request
from pathlib import Path

SKILL = Path(__file__).resolve().parent
TEMPLATE = SKILL / "template"
FONT_URL = "https://github.com/google/fonts/raw/main/ofl/bevietnampro/BeVietnamPro-Bold.ttf"


def env(name, root_env):
    if os.environ.get(name):
        return os.environ[name]
    if root_env.is_file():
        for line in root_env.read_text(encoding="utf-8").splitlines():
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip().strip('"')
    return ""


def main():
    styles = sorted(p.stem for p in (TEMPLATE / "style").glob("*.txt"))
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", help="short ascii name, e.g. bach-dang-938")
    ap.add_argument("--style", required=True, choices=styles, help="closest period style to start from")
    ap.add_argument("--dir", default="lich-su-vn", help="parent folder for projects (relative to cwd)")
    a = ap.parse_args()

    repo = Path.cwd()
    root_env = repo / ".env"
    dst = repo / a.dir / f"{a.slug}-long"
    if dst.exists():
        sys.exit(f"{dst} already exists")

    shutil.copytree(TEMPLATE / "script", dst / "script", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy(TEMPLATE / "style" / f"{a.style}.txt", dst / "script/style.txt")
    (dst / "script/vo.txt").write_text("", encoding="utf-8")
    (dst / "script/scenes.json").write_text("{}\n", encoding="utf-8")
    (dst / "script/video.json").write_text(json.dumps(
        {"numbers": [], "cues": [], "glue": ""}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (dst / "sources.md").write_text(f"# Nguồn fact: {a.slug}\n\n## Fact dùng được\n\n## Chỗ nguồn lệch nhau\n",
                                    encoding="utf-8")
    for sub in ("assets/img", "assets/audio", "assets/sfx", "assets/fonts", "build/logs"):
        (dst / sub).mkdir(parents=True, exist_ok=True)
    shutil.copytree(TEMPLATE / "assets/style-ref", dst / "assets/style-ref")

    font = dst / "assets/fonts/BeVietnamPro-Bold.ttf"
    try:
        urllib.request.urlretrieve(FONT_URL, font)
    except OSError as e:
        print(f"  font download failed ({e}); put BeVietnamPro-Bold.ttf in {font.parent}")

    if root_env.is_file():
        shutil.copy(root_env, dst / ".env")
    else:
        print("  no .env at repo root: create one with VIVIBE_API_KEY=... and VIVIBE_VOICE=...")
    music = env("HC_MUSIC_FILE", root_env)
    if music and Path(music).is_file():
        shutil.copy(music, dst / "assets/audio/music.mp3")
    sfx_dir = env("HC_SFX_DIR", root_env)
    if sfx_dir and Path(sfx_dir).is_dir():
        for f in Path(sfx_dir).glob("*.mp3"):
            shutil.copy(f, dst / "assets/sfx" / f.name)

    print(f"project -> {dst}")
    print("next: fill sources.md, script/vo.txt, script/scenes.json, script/video.json, adapt script/style.txt")


if __name__ == "__main__":
    main()
