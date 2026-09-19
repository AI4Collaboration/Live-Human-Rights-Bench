#!/usr/bin/env python3
"""
Backfill HUDOC metadata for an explicitly selected candidate Hub dataset.
Supply the date lookup produced by backfill_decision_dates.py with --dates.
Publication to that selected Hub dataset requires --push.
"""
import argparse, json, os, sys, time
from pathlib import Path
import requests
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hudoc_scraper import search_hudoc, parse_search_result  # noqa
from datasets import load_dataset

def backfill(missing, dates, batch, sleep):
    sess = requests.Session(); found = 0
    for b in range(0, len(missing), batch):
        chunk = missing[b:b+batch]
        q = 'contentsitename:ECHR AND (' + " OR ".join(f'itemid:"{i}"' for i in chunk) + ')'
        try:
            resp = search_hudoc(sess, q, 0, max(100, batch*2))
        except Exception as e:
            print("  batch err", e); time.sleep(2); continue
        for r in resp.get("results", []):
            rec = parse_search_result(r); iid = rec.get("item_id")
            if iid and rec.get("decision_date"):
                dates[iid] = {"decision_date": rec["decision_date"],
                              "application_number": rec.get("application_number", ""),
                              "importance": rec.get("importance", ""),
                              "ecli": rec.get("ecli", "")}
                found += 1
        time.sleep(sleep)
    return found

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--dates", required=True, help="Explicit HUDOC date-lookup JSON")
    ap.add_argument("--batch", type=int, default=50)
    ap.add_argument("--sleep", type=float, default=0.25)
    ap.add_argument("--push", action="store_true")
    a = ap.parse_args()

    dates = json.load(open(a.dates))
    ds = load_dataset(a.dataset, split="train")
    uniq = sorted({r["item_id"] for r in ds})
    missing = [i for i in uniq if not (i in dates and dates[i].get("decision_date"))]
    print(f"{a.dataset}: {len(ds)} pairs, {len(uniq)} cases, missing dates {len(missing)}")
    if missing:
        n = backfill(missing, dates, a.batch, a.sleep)
        json.dump(dates, open(a.dates, "w"), ensure_ascii=False)
        print(f"  backfilled {n}")

    def add(r):
        d = dates.get(r["item_id"], {})
        r["decision_date"] = d.get("decision_date", "")
        r["application_number"] = d.get("application_number", "")
        r["importance"] = d.get("importance", "")
        r["ecli"] = d.get("ecli", "")
        return r
    ds2 = ds.map(add)
    dated = sum(1 for x in ds2["decision_date"] if x)
    print(f"  dated pairs: {dated}/{len(ds2)} = {dated/len(ds2)*100:.1f}%")
    if a.push:
        ds2.push_to_hub(a.dataset,
            commit_message="Add decision_date/application_number/importance/ecli (HUDOC backfill)")
        print("  PUSHED", a.dataset)

if __name__ == "__main__":
    main()
