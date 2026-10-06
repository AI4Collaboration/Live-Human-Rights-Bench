#!/usr/bin/env python3
"""Regenerate the paraphrases that were cut at the generator's output cap.

    python quality_control/paraphrase/regenerate_cut.py \
        --out data/processed/paraphrase_texts_regen_cut.jsonl.gz

The targets come from `truncated` in quality_control/paraphrase/summary.json. Each is
rewritten again at light, medium and heavy with the generator's own paraphrase_text(),
same model and instructions; the only change is chunks(), which now splits over-long
lines on sentence ends so no chunk exceeds about 3,000 characters. The output has the
schema of paraphrase_texts.jsonl.gz (item_id, article, condition, text), including the
original rows, so it can replace those 104 rows once the evaluation is rerun on them.
"""

import argparse
import gzip
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from experiments.paraphrase_run import LEVELS, MAX_CHARS, PARAPHRASER, chunks, key, paraphrase_text  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--texts", default="data/processed/paraphrase_texts.jsonl.gz")
    p.add_argument("--preservation", default="quality_control/paraphrase/summary.json")
    p.add_argument("--out", default="data/processed/paraphrase_texts_regen_cut.jsonl.gz")
    p.add_argument("--checkpoint", default="data/experiments/paraphrase_regen_checkpoint.jsonl")
    p.add_argument("--limit", type=int, help="pilot on N targets")
    p.add_argument("--workers", type=int, default=26)
    a = p.parse_args()

    targets = sorted(json.load(open(a.preservation))["truncated"])
    if a.limit:
        targets = targets[:a.limit]
    wanted = set(targets)
    originals = {}
    for line in gzip.open(a.texts, "rt", encoding="utf-8"):
        r = json.loads(line)
        t = "%s|%s" % (r["item_id"], r["article"])
        if t in wanted and r["condition"] == "original":
            originals[t] = r["text"]
    missing = wanted - set(originals)
    if missing:
        sys.exit("No original text for %s" % sorted(missing))

    done = {}
    if os.path.exists(a.checkpoint):
        for line in open(a.checkpoint, encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                done[(r["target"], r["condition"])] = r["text"]
    lock = threading.Lock()
    k = key()

    def work(target, level):
        text = paraphrase_text(originals[target], LEVELS[level], k, PARAPHRASER)
        with lock, open(a.checkpoint, "a", encoding="utf-8", newline="\n") as h:
            h.write(json.dumps({"target": target, "condition": level, "text": text}, ensure_ascii=False) + "\n")
        return target, level, text

    jobs = [(t, lvl) for t in targets for lvl in LEVELS if (t, lvl) not in done]
    print("%d targets, %d rewrites to do, %d chunks each on average" % (
        len(targets), len(jobs),
        sum(len(chunks(originals[t][:MAX_CHARS])) for t in targets) // max(1, len(targets))), flush=True)
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(work, t, lvl) for t, lvl in jobs]
        for i, f in enumerate(as_completed(futs), 1):
            t, lvl, text = f.result()
            done[(t, lvl)] = text
            print("  %d/%d %s %s %d chars" % (i, len(jobs), t, lvl, len(text)), flush=True)

    with gzip.open(a.out, "wt", encoding="utf-8", newline="\n") as h:
        for t in targets:
            item_id, article = t.split("|")
            rows = [("original", originals[t])] + [(lvl, done[(t, lvl)]) for lvl in LEVELS]
            for cond, text in rows:
                h.write(json.dumps({"item_id": item_id, "article": article, "condition": cond,
                                    "text": text}, ensure_ascii=False) + "\n")
    print("wrote %d rows to %s" % (4 * len(targets), a.out))


if __name__ == "__main__":
    main()
