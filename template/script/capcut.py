"""CapCut desktop draft helpers: where drafts live, ids, and the building blocks from capcut_template.json."""
import json
import os
import uuid
from copy import deepcopy
from pathlib import Path

CAPCUT = Path(os.environ.get("CAPCUT_DRAFTS") or
              Path.home() / "AppData/Local/CapCut/User Data/Projects/com.lveditor.draft")
_TPL = Path(__file__).resolve().parent / "capcut_template.json"
TEMPLATE = json.loads(_TPL.read_text(encoding="utf-8"))
MAT = TEMPLATE["materials"]


def uid():
    """CapCut-style id: upper-case UUID with the third group lower-case."""
    u = str(uuid.uuid4()).upper().split("-")
    u[2] = u[2].lower()
    return "-".join(u)


def mat(kind):
    """A fresh copy of one template material (photo, audio, beat, text, audio_fade)."""
    return deepcopy(MAT[kind])


def aux(kind):
    """A fresh copy of one per-segment helper material (speeds, canvases, ...)."""
    return deepcopy(MAT["aux"][kind]) if kind in MAT["aux"] else mat("beat")


SEG_DEFAULTS = {
    "render_timerange": {"start": 0, "duration": 0}, "common_keyframes": [], "keyframe_refs": [],
    "speed": 1.0, "volume": 1.0, "last_nonzero_volume": 1.0, "visible": True, "state": 0,
    "desc": "", "group_id": "", "is_loop": False, "is_placeholder": False, "is_tone_modify": False,
    "reverse": False, "intensifies_audio": False, "cartoon": False, "enable_lut": False,
    "enable_adjust": False, "enable_hsl": False, "enable_color_curves": True,
    "enable_color_wheels": True, "enable_video_mask": True, "enable_hsl_curves": True,
    "enable_adjust_mask": False, "enable_color_adjust_pro": False,
    "enable_color_correct_adjust": False, "enable_color_match_adjust": False,
    "enable_mask_shadow": False, "enable_mask_stroke": False, "enable_smart_color_adjust": False,
    "track_attribute": 0, "template_id": "", "template_scene": "default", "source": 0,
    "hdr_settings": None, "caption_info": None, "color_correct_alg_result": "",
    "digital_human_template_group_id": "", "lyric_keyframes": None, "raw_segment_id": "",
    "segment_color_tag": 0, "uniform_scale": {"on": True, "value": 1.0},
    "responsive_layout": {"enable": False, "horizontal_pos_layout": 0, "size_layout": 0,
                          "target_follow": "", "vertical_pos_layout": 0},
}
