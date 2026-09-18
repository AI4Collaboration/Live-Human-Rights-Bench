#!/usr/bin/env python3
"""Remove Registry cover-headnote blocks from an explicitly supplied input.

Source attribution and review are still required before releasing the output.
This utility does not replace the current input acceptance records.
"""

import argparse, hashlib, json, os, sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "experiments"))
from headnote import find, strip        # noqa: E402


def file_digest(raw):
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", required=True)
    parser.add_argument("--field", default="full_case_text_no_verdict")
    parser.add_argument("--out", help="where to write the repaired corpus; defaults to --cases")
    parser.add_argument("--report", required=True)
    parser.add_argument("--apply", action="store_true", help="write it; default is a dry run")
    args = parser.parse_args()

    raw = open(args.cases, "rb").read()
    rows = json.loads(raw)
    field = args.field

    cuts, lengths = [], Counter()
    for index, row in enumerate(rows):
        text = row.get(field) or ""
        span = find(text)
        if span is None:
            continue
        removed = text[span[0]:span[1]]
        cuts.append({"index": index, "item_id": row.get("item_id"),
                     "article": row.get("article_full") or row.get("article"),
                     "characters_removed": len(removed),
                     "removed_head": removed[:200]})
        lengths[len(removed)] += 1
        if args.apply:
            row[field] = strip(text)

    if not cuts:
        print("No Registry block found; nothing to do.")
        return

    total = sum(c["characters_removed"] for c in cuts)
    print(f"{len(cuts)} of {len(rows)} rows carry the block, {total:,} characters, "
          f"median {sorted(c['characters_removed'] for c in cuts)[len(cuts)//2]:,}")

    report = {"status": "APPLIED" if args.apply else "DRY_RUN",
              "cases": args.cases, "field": field,
              "sha256_lf_before": file_digest(raw),
              "rows": len(rows), "rows_cut": len(cuts),
              "characters_removed": total, "cuts": cuts}

    if args.apply:
        out = args.out or args.cases
        blob = (json.dumps(rows, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        # The block and nothing else: every row must be its old self minus that span.
        check = json.loads(blob)
        old = json.loads(raw)
        assert len(check) == len(old), "row count changed"
        cut_at = {c["index"] for c in cuts}
        for i, (b, a) in enumerate(zip(old, check)):
            assert {k: v for k, v in b.items() if k != field} == \
                   {k: v for k, v in a.items() if k != field}, f"row {i}: metadata changed"
            if i not in cut_at:
                assert b[field] == a[field], f"row {i}: text changed without a cut"
            else:
                assert find(a[field] or "") is None, f"row {i}: block still present"
        open(out, "wb").write(blob)
        report["sha256_lf_after"] = file_digest(blob)
        report["out"] = out
        print(f"Wrote {out}")
    else:
        print("Dry run; pass --apply to write.")

    os.makedirs(os.path.dirname(os.path.abspath(args.report)), exist_ok=True)
    with open(args.report, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(f"Wrote {args.report}")


if __name__ == "__main__":
    main()
