"""Lay the regenerated rows over paraphrase_texts.jsonl.gz.

    python quality_control/paraphrase/regen/merge_texts.py \
        data/processed/paraphrase_texts.jsonl.gz data/processed/paraphrase_texts_regen_cut.jsonl.gz \
        <merged.jsonl.gz> <subset.jsonl.gz>

The merged file is the full set with the cut targets replaced, for the number check.
The subset holds every target of the affected judgments, for the claim check, which
runs per judgment. Originals must match exactly; the script stops otherwise.
"""
import gzip, json, os, sys

base, regen, merged, subset = sys.argv[1:5]
new = {}
for line in gzip.open(regen, "rt", encoding="utf-8"):
    r = json.loads(line)
    new[(r["item_id"], r["article"], r["condition"])] = r
items = {k[0] for k in new}
replaced = 0
with gzip.open(merged, "wt", encoding="utf-8", newline="\n") as m, \
        gzip.open(subset, "wt", encoding="utf-8", newline="\n") as s:
    for line in gzip.open(base, "rt", encoding="utf-8"):
        r = json.loads(line)
        k = (r["item_id"], r["article"], r["condition"])
        if k in new:
            if r["condition"] == "original":
                assert r["text"] == new[k]["text"], k
            elif r["text"] != new[k]["text"]:
                replaced += 1
            r = new[k]
        out = json.dumps(r, ensure_ascii=False) + "\n"
        m.write(out)
        # the subset keeps every target of an affected judgment, as the claim check runs per judgment
        if r["item_id"] in items:
            s.write(out)
print("replaced paraphrase rows:", replaced, "judgments in subset:", len(items))
