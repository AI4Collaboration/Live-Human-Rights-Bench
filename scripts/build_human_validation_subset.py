"""
Build a human-validation subset for the state-swap perturbation.

What reviewers actually ask is whether the perturbation preserved the facts of
the judgment. Comparing one arm against another cannot answer that: every arm of
a group is rendered from the SAME templated body, so outside the country
placeholder the two texts are identical by construction, and the programmatic
audit already guarantees it. An annotator looking at two arms can only catch a
leaked country name or broken grammar.

The comparison that carries information is source judgment vs rendered arm: it
covers the anonymise step, where respondent identity (state, demonym, cities,
courts) was detected and templated. That is the only place a fact could have
been damaged. This script therefore lays out three texts per sampled group:

  text_source  the verdict-free judgment the generator consumed (echr-verdict-free)
  text_real    control_original, i.e. the real respondent on the neutralised frame
  text_probe   the probe arm (Ukraine by default)

and asks separate questions of each pair.

Run: python scripts/build_human_validation_subset.py --n 40
"""
import argparse
import csv
import random
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "data" / "experiments" / "stateswap" / "human_validation_subset.csv"
STATESWAP_DATASET = "overthelex/echr-livehrb-stateswap"
SOURCE_DATASET = "overthelex/echr-verdict-free"

PROTOCOL = """HUMAN VALIDATION PROTOCOL (state-swap fact preservation)

Each row holds three versions of the same case:
  text_source  the judgment text as published, with the Court's own conclusion
               already removed. This is what the generator consumed.
  text_real    the same case after respondent identity was generalised, with the
               REAL respondent state filled back in (arm control_original).
  text_probe   the same templated body with the probe state filled in instead.

Answer per row:
 1. facts_preserved_vs_source (yes/no): comparing text_source with text_real, are
    all facts, dates, numbers, events, and legal reasoning identical? Generalised
    place, court, and authority names are expected and are NOT a fact change.
 2. generalisation_harmless (yes/no): where a name was generalised, does the text
    still support the same legal analysis? Answer no if a removed detail was
    legally material (for example a specific court's competence).
 3. no_original_country_in_probe (yes/no): does text_probe contain no surface form
    of the real respondent state, including demonyms, cities, and courts?
 4. only_country_changed (yes/no): comparing text_real with text_probe, does only
    the country and its adjective differ?
 5. reads_naturally (yes/no): does text_probe read like a normal judgment?
 6. notes: anything else (leaked country, broken grammar, changed fact).

Question 1 is the one reviewers care about; questions 3 to 5 are the cheap checks
the programmatic audit already covers and serve as a sanity floor.

Agreement = share of rows where questions 1 and 2 are both yes, plus
inter-annotator agreement on those two columns across 2+ annotators."""


def load_hf(name, split_hint="train"):
    try:
        from datasets import load_dataset
    except ImportError:
        print("ERROR: pip install datasets"); sys.exit(1)
    ds = load_dataset(name)
    split = split_hint if split_hint in ds else list(ds.keys())[0]
    return [dict(r) for r in ds[split]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--probe", default="probe_ukraine",
                    choices=["probe_ukraine", "probe_russia"])
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--stateswap-dataset", default=STATESWAP_DATASET)
    ap.add_argument("--source-dataset", default=SOURCE_DATASET)
    ap.add_argument("--output", type=Path, default=OUT)
    args = ap.parse_args()

    rows = load_hf(args.stateswap_dataset)
    print(f"Loaded {len(rows)} state-swap rows from {args.stateswap_dataset}")

    src_rows = load_hf(args.source_dataset)
    # item_id is unique per judgment; the same judgment can back several
    # case-article instances, and the verdict-free text is the same for all.
    source_text = {}
    for r in src_rows:
        iid = str(r.get("item_id", ""))
        txt = r.get("verdict_free_text") or r.get("full_case_text") or ""
        if iid and txt and iid not in source_text:
            source_text[iid] = txt
    print(f"Loaded {len(source_text)} source judgments from {args.source_dataset}")

    g = defaultdict(dict)
    for c in rows:
        g[c["swap_group_id"]][c["arm"]] = c

    eligible, missing_source = [], 0
    for gid, arms in g.items():
        if "control_original" not in arms or args.probe not in arms:
            continue
        if str(arms["control_original"]["item_id"]) not in source_text:
            missing_source += 1
            continue
        eligible.append(gid)
    if missing_source:
        print(f"WARNING: {missing_source} groups have no source text in "
              f"{args.source_dataset} and were skipped.")
    if not eligible:
        print("ERROR: no groups with both arms and a source text."); sys.exit(1)

    random.seed(args.seed)
    sample = random.sample(eligible, min(args.n, len(eligible)))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["swap_group_id", "item_id", "article", "real_country",
                    "probe_country", "text_source", "text_real", "text_probe",
                    "facts_preserved_vs_source", "generalisation_harmless",
                    "no_original_country_in_probe", "only_country_changed",
                    "reads_naturally", "annotator", "notes"])
        for gid in sample:
            o = g[gid]["control_original"]
            p = g[gid][args.probe]
            iid = str(o["item_id"])
            w.writerow([gid, iid, o.get("article_full") or o.get("article"),
                        o.get("respondent_original") or o.get("respondent"),
                        p.get("respondent"),
                        source_text[iid],
                        o.get("case_text_rendered", ""),
                        p.get("case_text_rendered", ""),
                        "", "", "", "", "", "", ""])

    print(f"\nWrote {len(sample)} rows to {args.output}")
    print(f"Pairings: source vs control_original (fact preservation), "
          f"control_original vs {args.probe} (country swap)\n")
    print(PROTOCOL)
    with open(args.output.parent / "human_validation_protocol.txt", "w") as f:
        f.write(PROTOCOL + "\n")


if __name__ == "__main__":
    main()
