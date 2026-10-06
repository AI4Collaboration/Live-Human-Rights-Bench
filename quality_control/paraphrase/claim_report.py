#!/usr/bin/env python3
"""Summarise a claim_coverage.py run.

    python quality_control/paraphrase/claim_report.py \
        --run quality_control/paraphrase/claims \
        --preservation quality_control/paraphrase/summary.json \
        --out quality_control/paraphrase/claims/summary.json \
        --per-target quality_control/paraphrase/claims/per_target.csv

The headline is conditional retention: of the claims the verifier finds in the
original text, the share it still finds in the paraphrase. Conditioning on the
original removes claims the extractor got wrong and the verifier's own misses,
which would otherwise be charged to the paraphrase. Rates are averaged per
target first, then across targets, so a long judgment does not outweigh a short
one; 95% intervals come from a bootstrap over judgments.
"""

import argparse
import collections
import csv
import gzip
import json
import os
import random
import statistics

LEVELS = ["light", "medium", "heavy"]


def read_jsonl(directory, name):
    """Rows of `name` or `name`.gz in `directory`."""
    path = os.path.join(directory, name)
    opener = open
    if not os.path.exists(path):
        path, opener = path + ".gz", gzip.open
    with opener(path, "rt", encoding="utf-8") as h:
        return [json.loads(line) for line in h if line.strip()]


def boot(values_by_item, reps=2000, seed=0):
    """Mean of per-item means with a bootstrap 95% interval over items."""
    items = [v for v in values_by_item.values() if v]
    means = [statistics.mean(v) for v in items]
    if not means:
        return None
    rng = random.Random(seed)
    draws = sorted(statistics.mean(rng.choice(means) for _ in means) for _ in range(reps))
    return {"mean": round(statistics.mean(means), 4), "lo": round(draws[int(.025 * reps)], 4),
            "hi": round(draws[int(.975 * reps) - 1], 4), "targets": len(means)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True)
    p.add_argument("--preservation", default="quality_control/paraphrase/summary.json")
    p.add_argument("--out", required=True)
    p.add_argument("--per-target", help="optional CSV, one row per target")
    a = p.parse_args()

    rows = read_jsonl(a.run, "claims.jsonl")
    swaps = read_jsonl(a.run, "swap_control.jsonl")
    config = json.load(open(os.path.join(a.run, "config.json")))
    truncated = set(json.load(open(a.preservation))["truncated"])

    # verdicts[(item, article, claim index)][condition] = bool or None
    verdicts = collections.defaultdict(dict)
    loss = collections.defaultdict(dict)
    meta = {}
    counter = collections.Counter()
    for r in rows:
        k = (r["item_id"], r["article"])
        idx = counter[(k, r["condition"])]
        counter[(k, r["condition"])] += 1
        verdicts[k + (idx,)][r["condition"]] = r["supported"]
        loss[k + (idx,)][r["condition"]] = r.get("loss_label")
        meta[k + (idx,)] = r

    def target(key):
        return "%s|%s" % (key[0], key[1])

    out = {"config": config, "judgments": len({k[0] for k in verdicts}),
           "targets": len({k[:2] for k in verdicts}),
           "claim_target_pairs": len(verdicts),
           "unverified_verdicts": sum(v is None for d in verdicts.values() for v in d.values())}
    out["claims_per_target_median"] = statistics.median(
        collections.Counter(target(k) for k in verdicts).values())

    for subset, keep in (("all", lambda t: True), ("without_truncated", lambda t: t not in truncated),
                         ("truncated_only", lambda t: t in truncated)):
        block = {}
        raw = collections.defaultdict(lambda: collections.defaultdict(list))
        cond = collections.defaultdict(lambda: collections.defaultdict(list))
        adj = collections.defaultdict(lambda: collections.defaultdict(list))
        for k, d in verdicts.items():
            t = target(k)
            if not keep(t) or d.get("original") is None:
                continue
            raw["original"][t].append(d["original"])
            for lvl in LEVELS:
                if d.get(lvl) is None:
                    continue
                raw[lvl][t].append(d[lvl])
                if d["original"]:
                    cond[lvl][t].append(d[lvl])
                    adj[lvl][t].append(d[lvl] or loss[k].get(lvl) == "present")
        block["supported_raw"] = {c: boot(raw[c]) for c in ["original"] + LEVELS}
        block["retention_given_original"] = {lvl: boot(cond[lvl]) for lvl in LEVELS}
        # The same, crediting losses the second look found "present" (verifier misses).
        block["retention_given_original_adjusted"] = {lvl: boot(adj[lvl]) for lvl in LEVELS}
        out[subset] = block

    # Where in the text the losses sit: retention by source position, clean targets vs cut ones.
    pos = collections.defaultdict(lambda: collections.defaultdict(list))
    for k, d in verdicts.items():
        if not d.get("original") or d.get("heavy") is None:
            continue
        group = "truncated" if target(k) in truncated else "clean"
        decile = min(int(meta[k]["position"] * 5), 4)
        pos[group]["%d-%d%%" % (decile * 20, decile * 20 + 20)].append(d["heavy"])
    out["heavy_retention_by_position"] = {
        g: {b: round(statistics.mean(v), 4) for b, v in sorted(bins.items())} for g, bins in pos.items()}

    # What the lost claims are: gone, rearranged, or a verifier miss.
    by_cond = collections.defaultdict(collections.Counter)
    for r in rows:
        if r["condition"] in LEVELS and r.get("loss_label"):
            group = "truncated" if "%s|%s" % (r["item_id"], r["article"]) in truncated else "clean"
            by_cond[(group, r["condition"])][r["loss_label"]] += 1
    out["lost_claims_by_label"] = {
        "%s/%s" % g: {lab: c[lab] for lab in ("absent", "altered", "present")} | {"total": sum(c.values())}
        for g, c in sorted(by_cond.items())}
    altered = [r for r in rows if r.get("loss_label") == "altered" and r["condition"] == "heavy"
               and "%s|%s" % (r["item_id"], r["article"]) not in truncated]
    out["examples_altered_in_heavy"] = [r["claim"] for r in random.Random(2).sample(altered, min(25, len(altered)))]

    judged = [s for s in swaps if s["supported"] is not None]
    out["swap_control"] = {"claims": len(judged),
                           "accepted_as_supported": round(sum(s["supported"] for s in judged) / len(judged), 4)
                           if judged else None}

    # Claims kept in the original but lost in heavy, clean targets only: for reading.
    lost = [meta[k]["claim"] for k, d in verdicts.items()
            if d.get("original") and d.get("heavy") is False and target(k) not in truncated]
    out["examples_lost_in_heavy"] = random.Random(1).sample(lost, min(25, len(lost)))
    out["swap_examples"] = [{"claim": s["claim"], "swapped": s["swapped"], "supported": s["supported"]}
                            for s in judged[:15]]
    if a.per_target:
        per = collections.defaultdict(lambda: collections.Counter())
        for k, d in verdicts.items():
            c = per[target(k)]
            c["claims"] += 1
            c["original_supported"] += bool(d.get("original"))
            for lvl in LEVELS:
                if d.get("original"):
                    c[lvl + "_kept"] += bool(d.get(lvl))
                    lab = loss[k].get(lvl)
                    if lab:
                        c["%s_%s" % (lvl, lab)] += 1
        fields = (["item_id", "article", "truncated", "claims", "original_supported"]
                  + ["%s_retention" % l for l in LEVELS]
                  + ["%s_%s" % (l, lab) for l in LEVELS for lab in ("absent", "altered", "present")])
        with open(a.per_target, "w", newline="", encoding="utf-8") as h:
            w = csv.writer(h, lineterminator="\n")
            w.writerow(fields)
            for t, c in sorted(per.items()):
                item, art = t.split("|")
                base = c["original_supported"]
                w.writerow([item, art, t in truncated, c["claims"], base]
                           + [round(c[l + "_kept"] / base, 4) if base else "" for l in LEVELS]
                           + [c["%s_%s" % (l, lab)] for l in LEVELS for lab in ("absent", "altered", "present")])

    json.dump(out, open(a.out, "w"), indent=2, ensure_ascii=False)
    print(json.dumps({k: v for k, v in out.items() if not k.endswith("examples")}, indent=2))


if __name__ == "__main__":
    main()
