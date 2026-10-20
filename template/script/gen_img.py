"""Generate one scene image with Codex image_gen (ChatGPT plan logged in to Codex CLI, no API key).

  python script/gen_img.py keo-phao-ngay              # text-only style lock
  python script/gen_img.py piroth --ref assets/img/keo-phao-ngay.png   # match an approved anchor

Output: assets/img/<name>.png, log at build/logs/<name>.log
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STYLE_FILE = "script/style.txt"
DEFAULT_REFS = ["assets/style-ref/anchor-E.jpg"]
SCENES = json.loads((ROOT / "script/scenes.json").read_text(encoding="utf-8"))
MAX_REFS = 5

ap = argparse.ArgumentParser()
ap.add_argument("name")
ap.add_argument("--ref", nargs="*", default=DEFAULT_REFS, help="style anchor images to match")
ap.add_argument("--style", default=STYLE_FILE)
ap.add_argument("--out")
a = ap.parse_args()
STYLE = (ROOT / a.style).read_text(encoding="utf-8").strip()

if a.name not in SCENES:
    sys.exit(f"unknown scene '{a.name}'. known: {', '.join(sorted(SCENES))}")
refs = [Path(r) if Path(r).is_absolute() else ROOT / r for r in a.ref][:MAX_REFS]
for r in refs:
    if not r.is_file():
        sys.exit(f"missing ref: {r}")

(ROOT / "build/logs").mkdir(parents=True, exist_ok=True)

scene = SCENES[a.name]
out = ROOT / (a.out or f"assets/img/{a.name}.png")

ref_note = ""
if refs:
    lines = "\n".join(
        f"Image {i}: a STYLE REFERENCE. Match its drawing style: line weight, colour palette, "
        f"brightness, flatness of fill, detail density, head-to-body ratio and face design. "
        f"Do not copy its composition, its subject or any text in it." for i in range(1, len(refs) + 1))
    ref_note = f"Attached images, in order:\n{lines}\n\n"

prompt = (
    "Use the built-in image_gen tool to generate exactly ONE image, landscape 16:9, 1920x1080, "
    "at the highest quality the tool offers.\n"
    + ref_note
    + "Use the text between <<< and >>> verbatim as the image prompt"
    + (", and pass the attached images to image_gen as style references" if refs else "")
    + f".\nAfter generating, copy the image to assets/img/{a.name}.png. "
      "Do not modify any other file. Print the saved path.\n\n"
    f"<<<\n{STYLE}\n\nSCENE: {SCENES[a.name]}\n>>>\n"
)

# lean image call: cheap model, low reasoning, no plugins/skills/hooks/apps/MCP loaded into context
GEN_MODEL, GEN_EFFORT = "gpt-5.6-luna", "low"
cmd = [shutil.which("codex"), "exec", "--skip-git-repo-check", "-s", "workspace-write", "-C", str(ROOT),
       "-m", GEN_MODEL, "-c", f"model_reasoning_effort={GEN_EFFORT}",
       "--disable", "plugins", "--disable", "hooks", "--disable", "apps", "-c", "mcp_servers={}"]
for r in refs:
    cmd += ["-i", str(r)]
cmd.append("-")

log = ROOT / f"build/logs/{Path(out).stem}.log"
with open(log, "w", encoding="utf-8") as fh:
    r = subprocess.run(cmd, input=prompt, text=True, encoding="utf-8",
                       stdout=fh, stderr=subprocess.STDOUT)
if out.is_file():                        # Codex sometimes saves its native size; normalise to 1920x1080
    from PIL import Image
    im = Image.open(out)
    if im.size != (1920, 1080):
        im.convert("RGB").resize((1920, 1080), Image.LANCZOS).save(out)
print(f"exit={r.returncode} " + (f"OK {out}" if out.is_file() else f"NO IMAGE, see {log}"))
