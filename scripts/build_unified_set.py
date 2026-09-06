"""
Build the ONE unified evaluation set (Terry: one set, ~800-1000 cases, spanning a
time window relatively evenly; recent is fine because we pick a model whose cutoff
sits mid-window for the contamination split).

Source = the leak-scrubbed static-2k HF set (verdict-free text + dates + labels
already computed). We drop Ukraine (country skew), keep 2012-2026 (the densely
covered, relatively even span), dedup to one row per (case, article), and carry a
stable pair_id so every axis (summarization / paraphrase / metadata / facts /
contamination / state-swap) runs on the SAME rows.

Prints the full distribution for verification. Writes data/processed/echr_unified.json.
Run: python scripts/build_unified_set.py [--cap N] [--min-year 2012] [--out ...]
"""
import argparse, json, random
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "data" / "processed" / "echr_livehrb_static_2k.json"
SEED = 12345

KEEP = ["item_id", "case_name", "respondent", "decision_date", "article",
        "article_full", "violation_label", "full_case_text_no_verdict",
        "application_number", "ecli", "importance"]


def yr(c):
    return int(str(c["decision_date"])[:4])


def quarter(c):
    m = int(str(c["decision_date"])[5:7])
    return f"{yr(c)}Q{(m - 1) // 3 + 1}"


def pair_id(c):
    return c.get("item_id") or c.get("ecli") or c.get("case_name")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-year", type=int, default=2012)
    ap.add_argument("--max-year", type=int, default=2026)
    ap.add_argument("--cap", type=int, default=0, help="max rows per year (0 = keep all)")
    ap.add_argument("--include-ukraine", action="store_true",
                    help="add Ukraine cases back (Terry wants ~1000 with some Ukraine)")
    ap.add_argument("--target", type=int, default=0,
                    help="trim to exactly N rows (seeded, drops violation cases from the biggest years)")
    ap.add_argument("--out", default=str(REPO / "data" / "processed" / "echr_unified.json"))
    args = ap.parse_args()

    raw = json.load(open(SRC))
    rows = [c for c in raw
            if (args.include_ukraine or str(c.get("respondent", "")).lower() != "ukraine")
            and c.get("decision_date")
            and args.min_year <= yr(c) <= args.max_year]

    # dedup to one row per (case, respondent, article)
    seen, dedup = set(), []
    for c in rows:
        k = (c.get("case_name"), c.get("respondent"), c.get("article"))
        if k in seen:
            continue
        seen.add(k)
        dedup.append(c)
    rows = dedup

    # optional per-year cap to even out the tail; seeded, prefer keeping no-violation
    # rows first so a cap does not worsen class balance.
    if args.cap:
        by_year = defaultdict(list)
        for c in rows:
            by_year[yr(c)].append(c)
        capped = []
        for y, cs in by_year.items():
            # priority: no-violation first (protects balance), then non-Ukraine violation
            # (keeps country diversity), then Ukraine violation (top-up only, kept minimal)
            def prio(c):
                uk = str(c.get("respondent", "")).lower() == "ukraine"
                if c["violation_label"] != "violation":
                    return 0
                return 2 if uk else 1
            random.Random(SEED + y).shuffle(cs)
            cs.sort(key=prio)
            capped.extend(cs[:args.cap] if len(cs) > args.cap else cs)
        rows = capped

    # trim to an exact round total, evenly: drop violation rows from the biggest years
    # first (never no-violation, to protect the class balance)
    if args.target and len(rows) > args.target:
        by_year = defaultdict(list)
        for c in rows:
            by_year[yr(c)].append(c)
        for y in by_year:
            random.Random(SEED * 2 + y).shuffle(by_year[y])
        drop = len(rows) - args.target
        while drop > 0:
            # biggest year that still has a violation row to spare
            cand = sorted(by_year, key=lambda y: -len(by_year[y]))
            for y in cand:
                # drop Ukraine violations first, then non-Ukraine violations, never no-violation
                uk_vi = [i for i, c in enumerate(by_year[y]) if c["violation_label"] == "violation"
                         and str(c.get("respondent", "")).lower() == "ukraine"]
                vi = uk_vi or [i for i, c in enumerate(by_year[y]) if c["violation_label"] == "violation"]
                if vi:
                    by_year[y].pop(vi[0]); drop -= 1; break
            else:
                break  # no violation rows left anywhere
        rows = [c for cs in by_year.values() for c in cs]

    out = []
    for c in rows:
        r = {k: c.get(k) for k in KEEP}
        r["pair_id"] = pair_id(c)
        out.append(r)

    json.dump(out, open(args.out, "w"), indent=1)

    # ---- report ----
    print(f"SOURCE {SRC.name}  ->  UNIFIED {Path(args.out).name}")
    print(f"window {args.min_year}-{args.max_year}  cap/yr={args.cap or 'none'}")
    print(f"\nN rows = {len(out)}   unique cases = {len(set(pair_id(c) for c in out))}"
          f"   respondents = {len(set(c['respondent'] for c in out))}")

    v = sum(1 for c in out if c["violation_label"] == "violation")
    print(f"violation = {v}  ({v/len(out):.0%})   no-violation = {len(out)-v}  ({(len(out)-v)/len(out):.0%})")

    byyr = Counter(yr(c) for c in out)
    print("\nper YEAR (n | violation%):")
    for y in sorted(byyr):
        yv = sum(1 for c in out if yr(c) == y and c["violation_label"] == "violation")
        print(f"  {y}: {byyr[y]:3d}  | {yv/byyr[y]:.0%}")
    ys = [byyr[y] for y in sorted(byyr)]
    print(f"per-year spread: min={min(ys)} max={max(ys)} ratio={max(ys)/min(ys):.1f}x")

    # per-quarter evenness (the real 'even' test)
    byq = Counter(quarter(c) for c in out)
    qs = sorted(byq)
    print(f"\nquarters covered: {len(qs)}  (from {qs[0]} to {qs[-1]})")
    qv = [byq[q] for q in qs]
    empty = [f"{args.min_year + i//4}Q{i%4+1}" for i in range((args.max_year-args.min_year+1)*4)
             if f"{args.min_year + i//4}Q{i%4+1}" not in byq]
    print(f"per-quarter: min={min(qv)} max={max(qv)} median~{sorted(qv)[len(qv)//2]}"
          + (f"  EMPTY quarters: {empty}" if empty else "  (no empty quarters)"))

    art = Counter(str(c.get("article")) for c in out)
    print("\ntop articles:", art.most_common(8))

    # contamination-split feasibility at a few candidate cutoffs
    print("\ncontamination split feasibility (pre / post at cutoff):")
    for cut in ("2023-01-01", "2023-07-01", "2024-01-01", "2024-07-01"):
        pre = sum(1 for c in out if str(c["decision_date"]) < cut)
        print(f"  cutoff {cut}:  pre={pre:4d}   post={len(out)-pre:4d}")

    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
