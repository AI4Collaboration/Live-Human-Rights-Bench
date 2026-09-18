#!/usr/bin/env python3
"""Quick summary-based state-swap (Terry): swap the respondent State in each case SUMMARY
to US / Russia / Ukraine and score, to test whether the verdict shifts by state identity.

Arms: original, US, Russia, Ukraine. Rule-based swap of the respondent country name and
demonym in the summary text (no generation model). 0-100 full-case prompt, 6-model roster.
Checkpointed per (model, case, arm).

  python experiments/stateswap_summary_run.py --model openai/gpt-5.6-sol
"""
from __future__ import annotations
import argparse, json, os, re, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "https://openrouter.ai/api/v1/chat/completions"
CASES = os.path.join(ROOT, "data/processed/echr_unified.json")
SUMMARIES = os.path.join(ROOT, "data/processed/summaries_dsv41flash.json")
OUT = os.path.join(ROOT, "data/experiments/stateswap_summary")
SYSTEM = ("The European Court of Human Rights (ECtHR) interprets the European Convention on "
          "Human Rights. You are a legal assistant specialised on the ECHR.")
PREDICTIVE = ("Below is a summary of the facts for an upcoming ECtHR case:\n\n{case_text}\n\n"
              "Target question: the ECtHR finds a violation of Article {article}?\n\n"
              "Based on the facts presented, state as a percentage from 0 to 100 how likely it is "
              "that the answer is yes.\n\n0 means certainly not, 50 genuinely uncertain, 100 certain. "
              "Use the whole range.\n\nProvide ONLY the number as your response.")

# Target states (name, demonym) to swap the respondent to.
TARGETS = {"US": ("the United States", "American"),
           "Russia": ("Russia", "Russian"),
           "Ukraine": ("Ukraine", "Ukrainian")}

# Demonyms for the respondent States present in the corpus (name -> adjective).
DEMONYM = {
    "ALBANIA": "Albanian", "ARMENIA": "Armenian", "AUSTRIA": "Austrian", "AZERBAIJAN": "Azerbaijani",
    "BELGIUM": "Belgian", "BOSNIA AND HERZEGOVINA": "Bosnian", "BULGARIA": "Bulgarian",
    "CROATIA": "Croatian", "CYPRUS": "Cypriot", "CZECH REPUBLIC": "Czech", "DENMARK": "Danish",
    "ESTONIA": "Estonian", "FINLAND": "Finnish", "FRANCE": "French", "GEORGIA": "Georgian",
    "GERMANY": "German", "GREECE": "Greek", "HUNGARY": "Hungarian", "ICELAND": "Icelandic",
    "IRELAND": "Irish", "ITALY": "Italian", "LATVIA": "Latvian", "LITHUANIA": "Lithuanian",
    "LUXEMBOURG": "Luxembourg", "MALTA": "Maltese", "MOLDOVA": "Moldovan", "MONTENEGRO": "Montenegrin",
    "NETHERLANDS": "Dutch", "NORTH MACEDONIA": "Macedonian", "NORWAY": "Norwegian", "POLAND": "Polish",
    "PORTUGAL": "Portuguese", "ROMANIA": "Romanian", "RUSSIA": "Russian", "SERBIA": "Serbian",
    "SLOVAKIA": "Slovak", "SLOVENIA": "Slovenian", "SPAIN": "Spanish", "SWEDEN": "Swedish",
    "SWITZERLAND": "Swiss", "TURKEY": "Turkish", "TÜRKIYE": "Turkish", "UKRAINE": "Ukrainian",
    "UNITED KINGDOM": "British",
}
RATING = re.compile(r"\b(100|\d{1,2})\b")


def title(name):
    return " ".join(w.capitalize() for w in name.split())


def swap(text, resp_name, target):
    """Replace the respondent country name + demonym with the target state's."""
    tgt_name, tgt_dem = TARGETS[target]
    resp_up = resp_name.upper().strip()
    src_name = title(resp_name)
    out = re.sub(rf"\b{re.escape(src_name)}\b", tgt_name, text)
    dem = DEMONYM.get(resp_up)
    if dem:
        out = re.sub(rf"\b{re.escape(dem)}\b", tgt_dem, out)
    return out


def call(model, prompt, k):
    body = {"model": model, "temperature": 1.0, "max_tokens": 2000,
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]}
    data = json.dumps(body).encode()
    for attempt in range(4):
        try:
            req = urllib.request.Request(URL, data=data, headers={"Authorization": f"Bearer {k}", "Content-Type": "application/json"})
            d = json.load(urllib.request.urlopen(req, timeout=180))
            return ((d.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        except Exception:
            if attempt == 3:
                return None
            time.sleep(2 * (attempt + 1))


def parse_rating(txt):
    if not txt:
        return None
    m = RATING.search(txt.strip())
    if not m:
        return None
    v = int(m.group(1))
    return v if 0 <= v <= 100 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--samples", type=int, default=10)
    ap.add_argument("--workers", type=int, default=60)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    k = os.environ["OPENROUTER_API_KEY"]
    cases = json.load(open(CASES))
    if a.limit:
        cases = cases[:a.limit]
    summaries = json.load(open(SUMMARIES))["summaries"]
    mdir = os.path.join(OUT, a.model.replace("/", "_"))
    os.makedirs(mdir, exist_ok=True)
    respath = os.path.join(mdir, "stateswap_summary_results.jsonl")
    done = {}
    if os.path.exists(respath):
        for line in open(respath):
            if line.strip():
                r = json.loads(line); done[r["key"]] = r
    lock = threading.Lock()
    arms = ["original"] + list(TARGETS)
    jobs = []
    for c in cases:
        summ = (summaries.get(c["item_id"]) or [None])[0]
        if not summ:
            continue
        resp = c.get("target_respondent") or c.get("respondent") or ""
        for arm in arms:
            jk = f"{c['item_id']}|{c['article_full']}|{arm}"
            if jk in done:
                continue
            text = summ if arm == "original" else swap(summ, resp, arm)
            jobs.append((jk, c, arm, text))
    print(f"{a.model}: {len(jobs)} (case,arm) units, arms={arms}", flush=True)

    def work(job):
        jk, c, arm, text = job
        prompt = PREDICTIVE.format(case_text=text, article=c["article_full"])
        ratings = [parse_rating(call(a.model, prompt, k)) for _ in range(a.samples)]
        good = [r for r in ratings if r is not None]
        avg = sum(good) / len(good) if good else None
        pred = None if avg is None else ("violation" if avg > 60 else "no_violation" if avg < 40 else "abstention")
        return {"key": jk, "item_id": c["item_id"], "article": c["article_full"],
                "respondent": c.get("target_respondent") or c.get("respondent"), "arm": arm,
                "violation_label": c["violation_label"], "avg_rating": avg, "prediction": pred,
                "accurate": pred == c["violation_label"], "n_unparsed": len(ratings) - len(good)}
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(work, j) for j in jobs]
        for i, f in enumerate(as_completed(futs), 1):
            with lock, open(respath, "a", encoding="utf-8", newline="\n") as h:
                h.write(json.dumps(f.result(), ensure_ascii=False) + "\n"); h.flush()
            if i % 200 == 0:
                print(f"  {i}/{len(jobs)}", flush=True)
    print(f"{a.model} done -> {respath}", flush=True)


if __name__ == "__main__":
    main()
