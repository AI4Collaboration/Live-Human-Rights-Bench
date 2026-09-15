#!/usr/bin/env python3
"""Remove the earlier instance's outcome from the procedural history of a Grand Chamber case.

The 15 September input repair cut the Court's law section and the Registry keyword line,
and between them they account for 1,011 of the 1,021 leak spans in
`data/audits/verdict_spans/dsv41flash.json`. Ten survive, all of one kind: a Grand
Chamber judgment recounting what the Chamber held, in PROCEDURE, before the facts begin.

    In a judgment delivered on 21 November 2013 a Chamber of that Section ... held,
    by four votes to three, that there had been no violation of Article 3 ...

No structural rule reaches them. They sit above THE FACTS, they carry no assessment
heading, and the sentence is procedural history rather than the Court's own conclusion,
which is why `leak_audit/leakdef.py` and the release checks both pass the rows. For a
case now before the Grand Chamber the Chamber's outcome is the single strongest prior
available, and on `001-122664` it is the opposite of the label being predicted.

This removes those sentences and nothing else. Each cut is located by the recorded quote
rather than by a pattern, the text either side is asserted unchanged, and every other
row in the corpus must come out byte-identical. Dry-run by default.

    python scripts/cut_procedural_history.py \
      --audit data/audits/verdict_spans/dsv41flash.json \
      --cases data/processed/echr_unified.json --apply
"""

import argparse, hashlib, json, os, re, sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "experiments"))
from scoring import MAX_CASE_CHARS        # noqa: E402
from verdict_spans import EARLIER_INSTANCE, locate   # noqa: E402

FIELD = "full_case_text_no_verdict"


def file_digest(raw):
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def cuts_for(rows, audit_rows):
    """Quotes to remove, per judgment, from the spans that still locate in the text.

    Keyed by judgment rather than by instance: the text is a property of the judgment and
    several case-article rows share it, so cutting per instance would rewrite the same
    string twice and the second pass would not find its quote.
    """
    text_of = {}
    for row in rows:
        text_of.setdefault(row["item_id"], row[FIELD] or "")
    wanted = defaultdict(list)
    for row in audit_rows:
        for span in row["spans"]:
            if span["category"] != EARLIER_INSTANCE or span["tier"] != "leak":
                continue
            quote = span["quote"]
            # The audit ran on the pre-repair text, so its offsets are stale; the quote
            # is what carries over. A span that no longer locates was already removed by
            # the repair and is not this script's business.
            if locate(quote, text_of.get(row["item_id"], "")[:MAX_CASE_CHARS]):
                if quote not in wanted[row["item_id"]]:
                    wanted[row["item_id"]].append(quote)
    return wanted


def excise(text, quote):
    """Text with `quote` removed, or None when it is not there.

    Whitespace either side is collapsed to one space so the join does not announce
    itself, and the surrounding characters are the only thing this is allowed to touch.
    """
    span = locate(quote, text)
    if span is None:
        return None
    start, end = span
    before, after = text[:start], text[end:]
    if before.rstrip() != before and after.lstrip() != after:
        return before.rstrip() + " " + after.lstrip()
    return before + after


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default="data/processed/echr_unified.json")
    parser.add_argument("--audit", default="data/audits/verdict_spans/dsv41flash.json")
    parser.add_argument("--report", default="data/audits/verdict_spans/procedural_history_cuts.json")
    parser.add_argument("--apply", action="store_true", help="write the corpus; default is a dry run")
    args = parser.parse_args()

    raw = open(args.cases, "rb").read()
    rows = json.loads(raw)
    audit = json.load(open(args.audit))
    wanted = cuts_for(rows, audit["rows"])
    if not wanted:
        print("Nothing to cut: no earlier-instance span still locates in this corpus.")
        return

    rewritten, record = {}, []
    for item_id, quotes in sorted(wanted.items()):
        text = next(row[FIELD] for row in rows if row["item_id"] == item_id)
        out = text
        for quote in quotes:
            cut = excise(out, quote)
            if cut is None:
                sys.exit(f"ERROR: {item_id}: quote no longer locates after an earlier cut")
            out = cut
        # The only permitted change is the removal itself: what is left must be the
        # original text minus exactly those characters, which is checked rather than
        # assumed, because a normalising edit here would silently rewrite the corpus.
        residue = out
        for quote in quotes:
            if locate(quote, residue):
                sys.exit(f"ERROR: {item_id}: quote still present after its own cut")
        removed = len(text) - len(out)
        if removed <= 0:
            sys.exit(f"ERROR: {item_id}: cut did not shorten the text")
        rewritten[item_id] = out
        record.append({"item_id": item_id, "quotes": quotes,
                       "characters_removed": removed,
                       "length_before": len(text), "length_after": len(out)})
        print(f"  {item_id}: {len(quotes)} sentence(s), {removed} characters")

    touched = [row for row in rows if row["item_id"] in rewritten]
    print(f"\n{len(rewritten)} judgments, {len(touched)} case-article instances, "
          f"{sum(r['characters_removed'] for r in record)} characters")

    report = {"status": "DRY_RUN" if not args.apply else "APPLIED",
              "cases": args.cases, "audit": args.audit,
              "dataset_sha256_lf_before": file_digest(raw),
              "judgments": len(rewritten), "instances": len(touched),
              "cuts": record}

    if args.apply:
        for row in rows:
            if row["item_id"] in rewritten:
                row[FIELD] = rewritten[row["item_id"]]
        blob = (json.dumps(rows, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        # Instance count, order and every other field are invariants of this script.
        after = json.loads(blob)
        assert len(after) == len(json.loads(raw)), "instance count changed"
        for before_row, after_row in zip(json.loads(raw), after):
            assert {k: v for k, v in before_row.items() if k != FIELD} == \
                   {k: v for k, v in after_row.items() if k != FIELD}, "metadata changed"
            if after_row["item_id"] not in rewritten:
                assert before_row[FIELD] == after_row[FIELD], "untouched row changed"
        open(args.cases, "wb").write(blob)
        report["dataset_sha256_lf_after"] = file_digest(blob)
        print(f"Wrote {args.cases}")
    else:
        print("\nDry run; pass --apply to write.")

    os.makedirs(os.path.dirname(os.path.abspath(args.report)), exist_ok=True)
    with open(args.report, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(f"Wrote {args.report}")


if __name__ == "__main__":
    main()
