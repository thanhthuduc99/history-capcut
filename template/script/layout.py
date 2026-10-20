"""Where exported files live and what they are called. One place, so export, project creation and
timeline building can never disagree.

  export/
    <slug>-capcut/                  drag THIS folder into CapCut's media panel
      Anh/<slug>-01-<scene>.png     one picture per shot, numbered in timeline order
      Voice/<slug>-voice.mp3
      Nhac/<slug>-nhac.mp3
      SFX/<slug>-sfx-<name>.mp3
    <slug>-phu-de.srt               CapCut cannot import .srt as media: Text > Import captions
    <slug>-timeline.txt             shot lengths, camera moves, SFX timings
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SLUG = ROOT.name.removesuffix("-long")
EXPORT = ROOT / "export"
MEDIA = EXPORT / f"{SLUG}-capcut"
SRT = EXPORT / f"{SLUG}-phu-de.srt"
TIMELINE = EXPORT / f"{SLUG}-timeline.txt"


def image(i, img):
    """Shot i's picture. A scene key like "07-kim-quy" loses its own number: the shot number leads."""
    name = img.split("-", 1)[1] if img[:2].isdigit() and "-" in img else img
    return MEDIA / "Anh" / f"{SLUG}-{i:02d}-{name}.png"


VOICE = MEDIA / "Voice" / f"{SLUG}-voice.mp3"
MUSIC = MEDIA / "Nhac" / f"{SLUG}-nhac.mp3"


def sfx(name):
    return MEDIA / "SFX" / f"{SLUG}-sfx-{name}"
