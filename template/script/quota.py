"""Print the Codex 5-hour and weekly usage % from the newest session file (no API call, no quota spent)."""
import glob
import json
import os

files = sorted(glob.glob(os.path.expanduser("~/.codex/sessions/*/*/*/*.jsonl")), key=os.path.getmtime)
for f in reversed(files[-40:]):
    last = None
    for line in open(f, encoding="utf-8", errors="ignore"):
        if '"rate_limits"' not in line:
            continue
        try:
            p = json.loads(line).get("payload") or {}
        except ValueError:
            continue
        rl = p.get("rate_limits") or (p.get("info") or {}).get("rate_limits")
        if rl and rl.get("primary"):
            last = rl
    if last:
        print(f"{last['primary']['used_percent']} {(last.get('secondary') or {}).get('used_percent')}")
        break
else:
    print("? ?")
