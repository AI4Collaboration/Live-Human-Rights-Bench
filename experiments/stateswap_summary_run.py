#!/usr/bin/env python3
"""Summary-based state swap: replace the respondent State in each case summary
to US / Russia / Ukraine and score, to test whether the verdict shifts by state identity.

Arms: original, US, Russia, Ukraine. Rule-based swap of the respondent country name and
demonym in the summary text (no generation model). 0-100 full-case prompt, 6-model roster.
Checkpointed per (model, case, arm).

  python experiments/stateswap_summary_run.py --model openai/gpt-5.6-sol
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, sys, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from experiments.input_gate import bind_run_inputs
from experiments.scoring import parse_rating

URL = "https://openrouter.ai/api/v1/chat/completions"
CASES = os.path.join(ROOT, "data/processed/echr_unified.json")
SUMMARIES = os.path.join(ROOT, "data/processed/summaries_dsv41flash.json")
OUT = os.path.join(ROOT, "data/experiments/stateswap_summary_new")
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

# Exact target_respondent value -> (name aliases to match, demonym). Aliases cover the
# forms that actually appear in the summaries (official name, short name, article).
COUNTRIES = {
    "Ukraine": (["Ukraine"], "Ukrainian"),
    "the Republic of Moldova": (["the Republic of Moldova", "Republic of Moldova", "Moldova"], "Moldovan"),
    "Russia": (["Russia", "the Russian Federation", "Russian Federation"], "Russian"),
    "Azerbaijan": (["Azerbaijan"], "Azerbaijani"), "Greece": (["Greece"], "Greek"),
    "Serbia": (["Serbia"], "Serbian"), "Armenia": (["Armenia"], "Armenian"),
    "Malta": (["Malta"], "Maltese"), "Albania": (["Albania"], "Albanian"),
    "Iceland": (["Iceland"], "Icelandic"), "Norway": (["Norway"], "Norwegian"),
    "Romania": (["Romania"], "Romanian"), "Latvia": (["Latvia"], "Latvian"),
    "Italy": (["Italy"], "Italian"), "Hungary": (["Hungary"], "Hungarian"),
    "Georgia": (["Georgia"], "Georgian"), "Cyprus": (["Cyprus"], "Cypriot"),
    "Bosnia and Herzegovina": (["Bosnia and Herzegovina", "Bosnia"], "Bosnian"),
    "Czechia": (["Czechia", "the Czech Republic", "Czech Republic"], "Czech"),
    "Croatia": (["Croatia"], "Croatian"), "Lithuania": (["Lithuania"], "Lithuanian"),
    "France": (["France"], "French"), "Montenegro": (["Montenegro"], "Montenegrin"),
    "Estonia": (["Estonia"], "Estonian"), "San Marino": (["San Marino"], "Sammarinese"),
    "the Netherlands": (["the Netherlands", "Netherlands"], "Dutch"),
    "Slovenia": (["Slovenia"], "Slovenian"), "Switzerland": (["Switzerland"], "Swiss"),
    "the United Kingdom": (["the United Kingdom", "United Kingdom", "the UK", "UK"], "British"),
    "Bulgaria": (["Bulgaria"], "Bulgarian"), "Spain": (["Spain"], "Spanish"),
    "Austria": (["Austria"], "Austrian"), "Portugal": (["Portugal"], "Portuguese"),
    "Sweden": (["Sweden"], "Swedish"), "Ireland": (["Ireland"], "Irish"),
    "Slovakia": (["Slovakia"], "Slovak"), "Germany": (["Germany"], "German"),
    "Poland": (["Poland"], "Polish"),
    "North Macedonia": (["North Macedonia", "the former Yugoslav Republic of Macedonia", "Macedonia"], "Macedonian"),
    "Türkiye": (["Türkiye", "Turkey"], "Turkish"), "Belgium": (["Belgium"], "Belgian"),
    "Finland": (["Finland"], "Finnish"), "Denmark": (["Denmark"], "Danish"),
    "Liechtenstein": (["Liechtenstein"], "Liechtenstein"),
    "Luxembourg": (["Luxembourg"], "Luxembourgish"), "Andorra": (["Andorra"], "Andorran"),
}


def swap(text, resp_name, target):
    """Replace the respondent country name (all forms) + demonym with the target state's."""
    tgt_name, tgt_dem = TARGETS[target]
    aliases, dem = COUNTRIES.get((resp_name or "").strip(), ([resp_name.strip()] if resp_name else [], None))
    out = text
    for a in sorted([x for x in aliases if x], key=len, reverse=True):
        out = re.sub(rf"\b{re.escape(a)}\b", tgt_name, out, flags=re.I)
    if dem:
        out = re.sub(rf"\b{re.escape(dem)}\b", tgt_dem, out, flags=re.I)
    out = re.sub(r"\ba (American)\b", r"an \1", out)  # tidy article before American
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


def bind_run_config(directory, args):
    config = {
        "version": "stateswap-summary-aliases-v2",
        "rating_parser": "anchored-percentage-v1",
        "model": args.model, "samples": args.samples, "limit": args.limit,
        "temperature": 1.0, "max_tokens": 2000,
        "targets": TARGETS, "country_aliases_and_demonyms": COUNTRIES,
        "prompt_sha256": hashlib.sha256((SYSTEM + PREDICTIVE).encode()).hexdigest(),
        "cases_sha256": hashlib.sha256(Path(args.cases).read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
        "summaries_sha256": hashlib.sha256(Path(args.summaries).read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
    }
    # Normalize tuples to their JSON representation before comparing checkpoints.
    config = json.loads(json.dumps(config))
    directory = Path(directory)
    marker = directory / "run_config.json"
    if marker.exists():
        if json.loads(marker.read_text(encoding="utf-8")) != config:
            raise ValueError("State Swap inputs or settings changed; use a new output directory")
    elif any(directory.glob("*.jsonl")):
        raise ValueError("Unversioned State Swap checkpoints require a new output directory")
    else:
        directory.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return config


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--samples", type=int, default=10)
    ap.add_argument("--workers", type=int, default=60)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--cases", default=CASES)
    ap.add_argument("--summaries", default=SUMMARIES)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    if a.samples < 1 or a.workers < 1 or a.limit < 0:
        ap.error("Use positive samples/workers and a nonnegative limit")
    mdir = os.path.join(a.out, a.model.replace("/", "_"))
    bind_run_inputs(mdir, a.cases, a.summaries)
    bind_run_config(mdir, a)
    k = os.environ["OPENROUTER_API_KEY"]
    cases = json.loads(Path(a.cases).read_text(encoding="utf-8"))
    if a.limit:
        cases = cases[:a.limit]
    summaries = json.loads(Path(a.summaries).read_text(encoding="utf-8"))["summaries"]
    os.makedirs(mdir, exist_ok=True)
    respath = os.path.join(mdir, "stateswap_summary_results.jsonl")
    done = {}
    if os.path.exists(respath):
        for line in open(respath, encoding="utf-8"):
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

    def score_once(prompt, retries=3):
        # Retry when the model returns an empty or unparseable response (not just on
        # network errors) — this is what left DeepSeek-v4-pro with null rows.
        attempts = []
        for _ in range(retries):
            response = call(a.model, prompt, k)
            attempts.append(response)
            r = parse_rating(response)
            if r is not None:
                return r, attempts
        return None, attempts

    def work(job):
        jk, c, arm, text = job
        prompt = PREDICTIVE.format(case_text=text, article=c["article_full"])
        sampled = [score_once(prompt) for _ in range(a.samples)]
        ratings = [rating for rating, _ in sampled]
        response_attempts = [attempts for _, attempts in sampled]
        responses = [attempts[-1] for attempts in response_attempts]
        good = [r for r in ratings if r is not None]
        avg = sum(good) / len(good) if good else None
        pred = None if avg is None else ("violation" if avg > 60 else "no_violation" if avg < 40 else "abstention")
        return {"key": jk, "item_id": c["item_id"], "article": c["article_full"],
                "respondent": c.get("target_respondent") or c.get("respondent"), "arm": arm,
                "text_changed": text != summaries[c["item_id"]][0],
                "violation_label": c["violation_label"], "avg_rating": avg, "prediction": pred,
                "ratings": ratings, "responses": responses,
                "response_attempts": response_attempts,
                "parse_retry_count": sum(len(attempts) - 1 for attempts in response_attempts),
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
