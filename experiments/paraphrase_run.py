#!/usr/bin/env python3
"""Paraphrase perturbation, 0-100 full-case scoring (consistent with summary + syco).

Two stages:
  generate  reword each case's verdict-free text at light/medium/heavy strength with a
            strong paraphraser (gpt-5.6-sol), chunked so long cases don't truncate.
  eval      score arms [original, light, medium, heavy] for the 6-model roster with the
            same full-case prompt used elsewhere. Checkpointed per (model, case, arm).

  python experiments/paraphrase_run.py generate
  python experiments/paraphrase_run.py eval --model openai/gpt-5.6-sol
"""
from __future__ import annotations
import argparse, json, os, re, sys, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "https://openrouter.ai/api/v1/chat/completions"
CASES = os.path.join(ROOT, "data/processed/echr_unified.json")
PAIRS = os.path.join(ROOT, "data/processed/paraphrase_pairs.json")
OUT = os.path.join(ROOT, "data/experiments/paraphrase")
PARAPHRASER = "openai/gpt-5.6-sol"
LEVELS = {"light": "Lightly reword: keep most wording, vary a few phrasings.",
          "medium": "Substantially reword and vary sentence structure, keep all facts.",
          "heavy": "Fully rewrite in different words and structure, keep every fact and number."}
SYSTEM = ("The European Court of Human Rights (ECtHR) interprets the European Convention on "
          "Human Rights. You are a legal assistant specialised on the ECHR.")
PREDICTIVE = ("Below is a summary of the facts for an upcoming ECtHR case:\n\n{case_text}\n\n"
              "Target question: the ECtHR finds a violation of Article {article}?\n\n"
              "Based on the facts presented, state as a percentage from 0 to 100 how likely it is "
              "that the answer is yes.\n\n0 means certainly not, 50 genuinely uncertain, 100 certain. "
              "Use the whole range.\n\nProvide ONLY the number as your response.")
MAX_CHARS = 50000
RATING = re.compile(r"\b(100|\d{1,2})\b")


def key():
    return os.environ["OPENROUTER_API_KEY"]


def call(model, messages, k, max_tokens=4000):
    body = {"model": model, "messages": messages, "temperature": 1.0, "max_tokens": max_tokens}
    data = json.dumps(body).encode()
    for attempt in range(4):
        try:
            req = urllib.request.Request(URL, data=data, headers={"Authorization": f"Bearer {k}", "Content-Type": "application/json"})
            d = json.load(urllib.request.urlopen(req, timeout=240))
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


def chunks(text, size=3000):
    parts, cur = [], ""
    for para in text.split("\n"):
        if len(cur) + len(para) > size and cur:
            parts.append(cur); cur = ""
        cur += para + "\n"
    if cur.strip():
        parts.append(cur)
    return parts


def paraphrase_text(text, instr, k, paraphraser):
    out = []
    for ch in chunks(text[:MAX_CHARS]):
        msg = [{"role": "user", "content": f"{instr}\nReturn only the rewritten text, no preamble.\n\n{ch}"}]
        r = call(paraphraser, msg, k, max_tokens=4000)
        out.append(r.strip() if r else ch)
    return "\n".join(out)


def append(path, row, lock):
    with lock, open(path, "a", encoding="utf-8", newline="\n") as h:
        h.write(json.dumps(row, ensure_ascii=False) + "\n"); h.flush()


def load_done(path, field="key"):
    d = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            if line.strip():
                r = json.loads(line); d[r[field]] = r
    return d


def stage_generate(a):
    k = key()
    cases = json.load(open(CASES))
    if a.limit:
        cases = cases[:a.limit]
    os.makedirs(os.path.dirname(PAIRS), exist_ok=True)
    jl = PAIRS + ".jsonl"
    done = load_done(jl)
    lock = threading.Lock()
    todo = [c for c in cases if f"{c['item_id']}|{c['article_full']}" not in done]
    print(f"generate: {len(todo)} cases to paraphrase", flush=True)

    def work(c):
        base = c.get("full_case_text_no_verdict") or ""
        row = {"key": f"{c['item_id']}|{c['article_full']}", "item_id": c["item_id"],
               "article": c["article_full"], "violation_label": c["violation_label"],
               "original": base}
        for lvl, instr in LEVELS.items():
            row[lvl] = paraphrase_text(base, instr, k, a.paraphraser)
        append(jl, row, lock)
        return row
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(work, c) for c in todo]
        for i, f in enumerate(as_completed(futs), 1):
            f.result()
            if i % 25 == 0:
                print(f"  {i}/{len(todo)}", flush=True)
    # consolidate jsonl -> json
    rows = list(load_done(jl).values())
    json.dump(rows, open(PAIRS, "w"))
    print(f"generate done: {len(rows)} cases -> {PAIRS}", flush=True)


def stage_eval(a):
    k = key()
    pairs = json.load(open(PAIRS)) if os.path.exists(PAIRS) else list(load_done(PAIRS + ".jsonl").values())
    if a.limit:
        pairs = pairs[:a.limit]
    model = a.model
    mdir = os.path.join(OUT, model.replace("/", "_"))
    os.makedirs(mdir, exist_ok=True)
    respath = os.path.join(mdir, "paraphrase_results.jsonl")
    done = load_done(respath)
    lock = threading.Lock()
    arms = ["original", "light", "medium", "heavy"]
    jobs = []
    for p in pairs:
        for arm in arms:
            jk = f"{p['key']}|{arm}"
            if jk in done:
                continue
            jobs.append((jk, p, arm))
    print(f"eval {model}: {len(jobs)} (case,arm) units", flush=True)

    def work(job):
        jk, p, arm = job
        text = p.get(arm) or p["original"]
        prompt = PREDICTIVE.format(case_text=text[:MAX_CHARS], article=p["article"])
        ratings = [parse_rating(call(model, [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}], k, 2000)) for _ in range(a.samples)]
        good = [r for r in ratings if r is not None]
        avg = sum(good) / len(good) if good else None
        # score = likelihood of a violation: high -> violation (matches run_perturbation thresholds)
        pred = None if avg is None else ("violation" if avg > 60 else "no_violation" if avg < 40 else "abstention")
        return {"key": jk, "item_id": p["item_id"], "article": p["article"], "arm": arm,
                "violation_label": p["violation_label"], "avg_rating": avg, "prediction": pred,
                "accurate": pred == p["violation_label"], "n_unparsed": len(ratings) - len(good)}
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(work, j) for j in jobs]
        for i, f in enumerate(as_completed(futs), 1):
            append(respath, f.result(), lock)
            if i % 200 == 0:
                print(f"  {i}/{len(jobs)}", flush=True)
    print(f"eval {model} done -> {respath}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="stage", required=True)
    g = sub.add_parser("generate"); g.add_argument("--workers", type=int, default=40); g.add_argument("--limit", type=int, default=0); g.add_argument("--paraphraser", default=PARAPHRASER)
    e = sub.add_parser("eval"); e.add_argument("--model", required=True); e.add_argument("--samples", type=int, default=10); e.add_argument("--workers", type=int, default=60); e.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    (stage_generate if a.stage == "generate" else stage_eval)(a)


if __name__ == "__main__":
    main()
