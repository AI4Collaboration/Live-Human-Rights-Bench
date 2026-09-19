#!/usr/bin/env python3
"""Drop checkpoint rows whose samples did not all come back, so resume redoes them.

A checkpoint marks each completed target as done even when some ratings failed.
This helper selects incomplete baseline/summary rows for a resumed new run.

    python scripts/prune_degraded.py --run-dir data/experiments/fullcase_new
    python scripts/prune_degraded.py --run-dir data/experiments/fullcase_new --apply

Dry by default: it reports what it would remove and changes nothing until --apply.
"""

import argparse, json, os, shutil


def degraded(row):
    """True when any sample in this row failed to produce a rating."""
    if row.get("n_unparsed", 0) > 0:
        return True
    ratings = row.get("ratings")
    return bool(ratings) and any(r is None for r in ratings)


def prune(path, apply):
    rows = []
    for line in open(path):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue          # a torn final line from a hard kill
    keep = [r for r in rows if not degraded(r)]
    dropped = len(rows) - len(keep)
    if dropped and apply:
        shutil.copy2(path, path + ".bak")
        with open(path, "w") as f:
            for r in keep:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(rows), dropped


def main():
    p = argparse.ArgumentParser(description="Remove degraded rows so resume redoes them")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--apply", action="store_true", help="write the changes (default: report only)")
    args = p.parse_args()

    total = removed = 0
    for model in sorted(os.listdir(args.run_dir)):
        for arm in ("baseline", "rq1"):
            path = os.path.join(args.run_dir, model, arm + ".jsonl")
            if not os.path.exists(path):
                continue
            n, d = prune(path, args.apply)
            total += n
            removed += d
            if d:
                print("  %-28s %-9s %6d rows, %4d degraded" % (model, arm, n, d))

    verb = "removed" if args.apply else "would remove"
    print("\n%d rows total, %s %d (%.2f%%)" % (total, verb, removed, 100.0 * removed / max(total, 1)))
    if removed and not args.apply:
        print("re-run with --apply to write it; the results JSONs are rebuilt by the next run")
    elif removed:
        print("originals kept alongside as .bak; resume the original command with the same run directory")


if __name__ == "__main__":
    main()
