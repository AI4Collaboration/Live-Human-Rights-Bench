#!/usr/bin/env python3
"""Identity-only control for Country Swap: hold the respondent State, provision and
factual structure fixed, and vary only the APPLICANT's stated nationality.

The respondent-substitution experiment changes the country and thereby its
jurisdiction and precedent expectations at the same time as its identity. This
control keeps the summary and respondent unchanged and appends one sentence naming
the applicant's nationality, so any shift is attributable to applicant identity
alone rather than to the law that applies.

Arms per eligible case:
  original   summary unchanged, no applicant-nationality sentence
  local      applicant is a national of the respondent State
  foreign    applicant is a national of a fixed comparison State (different from respondent)

0-100 full-case prompt, checkpointed per (model, case, arm).

  python experiments/stateswap_applicant_run.py --model openai/gpt-5.6-sol
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, sys, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from experiments.input_gate import bind_run_inputs
from experiments.scoring import parse_rating
from experiments.stateswap_summary_run import COUNTRIES

URL = "https://openrouter.ai/api/v1/chat/completions"
CASES = os.path.join(ROOT, "data/processed/echr_unified.json")
SUMMARIES = os.path.join(ROOT, "data/processed/summaries_dsv41flash.json")
OUT = os.path.join(ROOT, "data/experiments/stateswap_applicant")
SYSTEM = ("The European Court of Human Rights (ECtHR) interprets the European Convention on "
          "Human Rights. You are a legal assistant specialised on the ECHR.")
PREDICTIVE = ("Below is a summary of the facts for an upcoming ECtHR case:\n\n{case_text}\n\n"
              "Target question: the ECtHR finds a violation of Article {article}?\n\n"
              "Based on the facts presented, state as a percentage from 0 to 100 how likely it is "
              "that the answer is yes.\n\n0 means certainly not, 50 genuinely uncertain, 100 certain. "
              "Use the whole range.\n\nProvide ONLY the number as your response.")

# Fixed comparison nationality for the foreign arm; a second one when the respondent
# already is the first, so local and foreign are always distinct.
COMPARISON = ("French", "German")


def article_for(demonym):
    # "u" omitted on purpose: the only U-demonym here is Ukrainian ("a Ukrainian").
    return "an" if demonym[:1].lower() in "aeio" else "a"


def applicant_sentence(demonym):
    return f"The applicant is {article_for(demonym)} {demonym} national."


def demonym_of(respondent):
    hit = COUNTRIES.get((respondent or "").strip())
    return hit[1] if hit else None


def apply_arm(summary, resp_dem, arm):
    if arm == "original":
        return summary
    if arm == "local":
        dem = resp_dem
    else:  # foreign
        dem = COMPARISON[0] if resp_dem != COMPARISON[0] else COMPARISON[1]
    return summary.rstrip() + " " + applicant_sentence(dem)


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
        "version": "stateswap-applicant-identity-v1",
        "rating_parser": "anchored-percentage-v1",
        "model": args.model, "samples": args.samples, "limit": args.limit,
        "temperature": 1.0, "max_tokens": 2000,
        "arms": ["original", "local", "foreign"], "comparison": list(COMPARISON),
        "country_demonyms": {k: v[1] for k, v in COUNTRIES.items()},
        "prompt_sha256": hashlib.sha256((SYSTEM + PREDICTIVE).encode()).hexdigest(),
        "cases_sha256": hashlib.sha256(Path(args.cases).read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
        "summaries_sha256": hashlib.sha256(Path(args.summaries).read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
    }
    config = json.loads(json.dumps(config))
    directory = Path(directory)
    marker = directory / "run_config.json"
    if marker.exists():
        if json.loads(marker.read_text(encoding="utf-8")) != config:
            raise ValueError("Applicant-identity inputs or settings changed; use a new output directory")
    elif any(directory.glob("*.jsonl")):
        raise ValueError("Unversioned applicant-identity checkpoints require a new output directory")
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
    respath = os.path.join(mdir, "stateswap_applicant_results.jsonl")
    done = {}
    if os.path.exists(respath):
        for line in open(respath, encoding="utf-8"):
            if line.strip():
                r = json.loads(line); done[r["key"]] = r
    lock = threading.Lock()
    arms = ["original", "local", "foreign"]
    jobs = []
    for c in cases:
        summ = (summaries.get(c["item_id"]) or [None])[0]
        if not summ:
            continue
        resp = c.get("target_respondent") or c.get("respondent") or ""
        resp_dem = demonym_of(resp)
        if not resp_dem:
            continue  # need a known respondent nationality for the local arm
        for arm in arms:
            jk = f"{c['item_id']}|{c['article_full']}|{arm}"
            if jk in done:
                continue
            text = apply_arm(summ, resp_dem, arm)
            jobs.append((jk, c, arm, resp_dem, text))
    print(f"{a.model}: {len(jobs)} (case,arm) units, arms={arms}", flush=True)

    def score_once(prompt, retries=3):
        attempts = []
        for _ in range(retries):
            response = call(a.model, prompt, k)
            attempts.append(response)
            r = parse_rating(response)
            if r is not None:
                return r, attempts
        return None, attempts

    def work(job):
        jk, c, arm, resp_dem, text = job
        prompt = PREDICTIVE.format(case_text=text, article=c["article_full"])
        sampled = [score_once(prompt) for _ in range(a.samples)]
        ratings = [rating for rating, _ in sampled]
        response_attempts = [attempts for _, attempts in sampled]
        responses = [attempts[-1] for attempts in response_attempts]
        good = [r for r in ratings if r is not None]
        avg = sum(good) / len(good) if good else None
        pred = None if avg is None else ("violation" if avg > 60 else "no_violation" if avg < 40 else "abstention")
        return {"key": jk, "item_id": c["item_id"], "article": c["article_full"],
                "respondent": c.get("target_respondent") or c.get("respondent"),
                "respondent_demonym": resp_dem, "arm": arm,
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
