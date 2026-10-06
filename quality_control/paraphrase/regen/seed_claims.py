"""Seed a claim-check run for the regenerated targets from the full run's calls.

    python quality_control/paraphrase/regen/seed_claims.py \
        <full run>/calls.jsonl quality_control/paraphrase/summary.json <new run dir>


Keeps every extraction for the affected judgments (same claims as before) and every
verdict whose text did not change: the original condition everywhere, and all
conditions of targets that were not regenerated. Drops verify/classify rows of the
regenerated paraphrases so they are checked afresh.
"""
import json, os, sys

full_calls, preservation, out_dir = sys.argv[1:4]
cut = set(json.load(open(preservation))["truncated"])
items = {t.split("|")[0] for t in cut}
os.makedirs(out_dir, exist_ok=True)
kept = dropped = 0
with open(os.path.join(out_dir, "calls.jsonl"), "w", encoding="utf-8", newline="\n") as h:
    for line in open(full_calls, encoding="utf-8"):
        r = json.loads(line)
        parts = r["key"].split("|")
        kind = parts[0]
        if parts[1] not in items or kind.startswith("swap"):
            continue
        if kind in ("verify", "classify"):
            target, cond = "%s|%s" % (parts[1], parts[2]), parts[3]
            if target in cut and cond != "original":
                dropped += 1
                continue
        h.write(line if line.endswith("\n") else line + "\n")
        kept += 1
print("seeded", kept, "rows; dropped", dropped, "verdict rows of regenerated paraphrases; judgments", len(items))
