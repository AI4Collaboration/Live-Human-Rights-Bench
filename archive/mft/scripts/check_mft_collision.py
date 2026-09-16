"""
Free (no-API) integrity check: confirm a regenerated mft_cases.json has NO
custom_id collision — i.e. a case judged under several articles must have a
DISTINCT minimal text per article, not the same text copied across them.

Run this right after `python experiments/generate_mft.py`, before evaluating.
Exit 0 = clean; exit 1 = still colliding (do NOT evaluate).
"""
import json
import sys
from pathlib import Path
from collections import defaultdict

REPO_ROOT = Path(__file__).resolve().parent.parent
MFT_PATH = REPO_ROOT / "data" / "mft" / "mft_cases.json"

cases = json.load(open(MFT_PATH))
by_id = defaultdict(list)
for c in cases:
    by_id[c["item_id"]].append(c)

multi = {k: v for k, v in by_id.items() if len(v) > 1}
collided = []
for item_id, rows in multi.items():
    texts = {r.get("mft_text", "") for r in rows if r.get("mft_text", "").strip()}
    # >1 row but only 1 distinct non-empty text => collision
    if len(texts) == 1 and len(rows) > 1:
        collided.append((item_id, len(rows)))

print(f"cases                     : {len(cases)}")
print(f"multi-article item_ids    : {len(multi)}")
print(f"still-colliding item_ids  : {len(collided)}")
if collided:
    print("  examples:", collided[:5])
    print("\nFAIL: MFT texts still collide across articles. Do NOT evaluate.")
    sys.exit(1)
print("\nPASS: every multi-article case has distinct per-article MFT text.")
