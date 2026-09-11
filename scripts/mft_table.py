"""Regenerate the MFT table in the appendix from the committed run outputs.

The appendix results block is disabled with `\\iffalse` and carries a note saying
nothing goes back in without verified source data and a traceable analysis artifact.
This is that artifact for the MFT table: it reads `data/experiments/mft/*.csv` and
nothing else, so the table can be checked rather than trusted.

Two definitions matter, because both have a plausible alternative that gives a
different number:

* **Pass rate** is the share of cases the model got right, not balanced accuracy.
  The MFT set is outcome-imbalanced, which is why the caption calls these a sanity
  check rather than evidence of competence.
* **Abstention** is the share of *samples* that abstained, not the share of cases
  where abstention won the vote. On Qwen3-32B those are 12.6 and 6.9 percent.

    python scripts/mft_table.py
"""
import collections
import csv
import glob
import os
import re
import sys

NAMES = {"claude-opus-4.8": "Claude Opus 4.8", "gpt-5.6": "GPT-5.6",
         "gemini-3.5-flash": "Gemini 3.5 Flash", "deepseek-v4": "DeepSeek-V4",
         "deepseek-v4-flash": "DeepSeek-V4-flash", "qwen3-235b": "Qwen3-235B",
         "qwen3-32b": "Qwen3-32B", "qwen3-8b": "Qwen3-8B"}
ORDER = list(NAMES)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main(root="data/experiments/mft"):
    runs = {}
    for p in sorted(glob.glob(os.path.join(root, "*_mft_samples*.csv"))):
        key = re.sub(r"_mft_samples\d+\.csv$", "", os.path.basename(p))
        runs[key] = read(p)
    missing = [k for k in ORDER if k not in runs]
    if missing:
        sys.exit("no run output for: %s" % ", ".join(missing))

    failed_everywhere = None
    for key in ORDER:
        wrong = {(r["case_name"], r["article"]) for r in runs[key]
                 if str(r["is_accurate"]).lower() not in ("true", "1")}
        failed_everywhere = wrong if failed_everywhere is None else failed_everywhere & wrong

    for key in ORDER:
        rows = runs[key]
        passed = sum(1 for r in rows if str(r["is_accurate"]).lower() in ("true", "1"))
        samples = sum(int(r["num_samples"]) for r in rows)
        abstained = sum(int(r["num_abstentions"]) for r in rows)
        print("%-20s & %.1f\\%% & %.1f\\%% \\\\"
              % (NAMES[key], 100.0 * passed / len(rows), 100.0 * abstained / samples))

    n = len(runs[ORDER[0]])
    print()
    print("%% %d of %d cases fail across all %d models" % (len(failed_everywhere), n, len(ORDER)))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/experiments/mft")
