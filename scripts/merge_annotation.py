"""Build data/annotation/annotation_merged.csv from the returned annotation sheets.

This is the step between the sheets the annotators sent back and the table the paper
and scripts/score_annotation.py are built on. It is committed so the published table
can be traced to a rule rather than to a spreadsheet session, but it cannot be re-run
from a clone: its three inputs identify the annotators and are deliberately not in the
repository.

    sent/       the sheets as shipped, annotator{1,2,3}.csv
    returned/   the same sheets with the label column filled in
    private/    control_key.csv, strata.csv, and assignment.csv mapping
                letter -> returned file -> sent sheet

    python scripts/merge_annotation.py --sent ... --returned ... --private ... \
        --out data/annotation/annotation_merged.csv

Annotators appear in the output only as the letters A to D. Which letter is which
person is held outside the repository, so the published table carries the labels and
not the people who wrote them.
"""
import argparse, csv, os, re
from collections import Counter

# Controls whose renumbering happened to land on a paragraph that genuinely is the
# source, so `yes` is the correct answer and the key demanded `no`. Established by
# reading all 19 controls by hand rather than by trusting the key, which records the
# intent of the construction and therefore reproduces its bug. P053 was caught by the
# annotators. See docs/ANNOTATION.md.
DEFECTIVE = {"P014", "P073", "P095", "P053"}

# "see paragraph 18 above", "see, in this connection, paragraphs 13-15 above" and
# "(paragraph 5 above)" all have to match: an earlier version required the word "see"
# immediately before the number and reported broken pairs that were never broken.
CIT = re.compile(r"paragraphs?\s+((?:\d+[\s,]*(?:to|and|-|–|—)?[\s,]*)+)(?:above|below)", re.I)


def cite_groups(text):
    """Every set of paragraph numbers the reasoning points at, one set per citation."""
    out = []
    for m in CIT.finditer(re.sub(r"\s+", " ", text)):
        inner, nums = m.group(1), set()
        for a, b in re.findall(r"(\d+)\s*(?:-|–|—|to)\s*(\d+)", inner):
            a, b = int(a), int(b)
            if b >= a and b - a < 200:
                nums.update(range(a, b + 1))
        for x in re.findall(r"\d+", re.sub(r"(\d+)\s*(?:-|–|—|to)\s*(\d+)", "", inner)):
            nums.add(int(x))
        if nums:
            out.append(nums)
    return out


def cite_class(row):
    """Whether the shown paragraph is cited alone, only inside a range, or not at all.

    The distinction decides which controls can be scored: where the Court points at a
    range and we show one of its members, the brief tells the annotator to answer
    `unclear`, so a `no` key would be scoring them against an instruction they were
    told to follow.
    """
    shown = int(row["cited_number"])
    hosts = [g for g in cite_groups(row["reasoning"]) if shown in g]
    if not hosts:
        return "uncited"
    return "single" if any(len(g) == 1 for g in hosts) else "range"


def read(path):
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main(sent, returned, private, out):
    assignment = read(os.path.join(private, "assignment.csv"))
    key = {r["pair_id"]: r for r in read(os.path.join(private, "control_key.csv"))}
    strata = {r["pair_id"]: r for r in read(os.path.join(private, "strata.csv"))}

    items = {}
    for sheet in sorted({a["sent_file"] for a in assignment}):
        for r in read(os.path.join(sent, sheet)):
            items.setdefault(r["pair_id"], r)

    letters = [a["letter"] for a in assignment]
    labels = {a["letter"]: {r["pair_id"]: r
                            for r in read(os.path.join(returned, a["returned_file"]))}
              for a in assignment}

    rows = []
    for pid in sorted(items):
        it, k = items[pid], key[pid]
        cc = cite_class(it)
        status = ""
        if k["kind"] == "control":
            status = ("defective" if pid in DEFECTIVE
                      else "excused" if cc == "range" else "scoreable")
        rec = {"pair_id": pid, "kind": k["kind"], "control_status": status,
               "expected": k["expected"], "accepts_unclear": k["accepts_unclear"],
               "pointer_kind": strata[pid]["pointer_kind"], "cite_class": cc,
               "sheets": strata[pid]["sheets"], "case_name": it["case_name"],
               "article": it["article"], "cited_number": it["cited_number"],
               "reasoning": it["reasoning"], "cited_fact": it["cited_fact"],
               "full_judgment": it["full_judgment"]}
        for letter in letters:
            r = labels[letter].get(pid)
            rec["label_%s" % letter] = r["label"].strip().lower() if r else ""
            rec["notes_%s" % letter] = r["notes"].strip() if r else ""
        rows.append(rec)

    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    # The line terminator is pinned: left to the platform, a checkout on another machine
    # rewrites every line and the artefact forks into two copies that differ by newline.
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    print("%d items written to %s" % (len(rows), out))
    print("  kind        :", dict(Counter(r["kind"] for r in rows)))
    print("  control_stat:", dict(Counter(r["control_status"]
                                          for r in rows if r["kind"] == "control")))
    print("  cite_class  :", dict(Counter(r["cite_class"] for r in rows)))
    for letter in letters:
        got = [r for r in rows if r["label_%s" % letter]]
        print("  %s  %d labels  %s" % (letter, len(got),
                                       dict(Counter(r["label_%s" % letter] for r in got))))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--sent", required=True, help="directory of the sheets as shipped")
    p.add_argument("--returned", required=True, help="directory of the filled-in sheets")
    p.add_argument("--private", required=True,
                   help="directory holding control_key.csv, strata.csv, assignment.csv")
    p.add_argument("--out", default="data/annotation/annotation_merged.csv")
    main(**vars(p.parse_args()))
