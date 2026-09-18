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
import argparse, hashlib, json, os, sys, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from experiments.input_gate import verify_cases
from experiments.scoring import parse_rating

URL = "https://openrouter.ai/api/v1/chat/completions"
CASES = os.path.join(ROOT, "data/processed/echr_unified.json")
PAIRS = os.path.join(ROOT, "data/processed/paraphrase_pairs_new.json")
OUT = os.path.join(ROOT, "data/experiments/paraphrase_new")
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
        if not r or not r.strip():
            raise RuntimeError("Paraphrase generation failed; no original-text fallback is recorded")
        out.append(r.strip())
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
    cases = json.loads(Path(a.cases).read_text(encoding="utf-8"))
    verify_cases(cases)
    k = key()
    if a.limit:
        cases = cases[:a.limit]
    os.makedirs(os.path.dirname(a.pairs) or ".", exist_ok=True)
    jl = a.pairs + ".jsonl"
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
    Path(a.pairs).write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    print(f"generate done: {len(rows)} cases -> {a.pairs}", flush=True)


def load_pairs(path):
    source = Path(path)
    if source.exists():
        pairs = json.loads(source.read_text(encoding="utf-8"))
    elif Path(str(source) + ".jsonl").exists():
        pairs = list(load_done(str(source) + ".jsonl").values())
    else:
        raise FileNotFoundError(f"Paraphrase inputs not found: {source}. Generate or supply --pairs first.")
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("Paraphrase input must contain completed original/light/medium/heavy records")
    seen = set()
    for row in pairs:
        identity = (row.get("item_id"), row.get("article"))
        if not all(identity) or identity in seen or row.get("key") != "|".join(identity):
            raise ValueError("Invalid or duplicate paraphrase case/provision identity")
        seen.add(identity)
        if any(not isinstance(row.get(arm), str) or not row[arm].strip()
               for arm in ["original", *LEVELS]):
            raise ValueError(f"Missing paraphrase arm for {row['key']}; original-text substitution is not allowed")
    return pairs


def bind_eval_config(directory, pairs, args):
    config = {
        "version": "paraphrase-provision-v1",
        "rating_parser": "anchored-percentage-v1",
        "model": args.model, "samples": args.samples, "temperature": 1.0,
        "max_case_chars": MAX_CHARS,
        "input_sha256": hashlib.sha256(
            json.dumps(pairs, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest(),
        "prompt_sha256": hashlib.sha256((SYSTEM + PREDICTIVE).encode("utf-8")).hexdigest(),
    }
    directory = Path(directory)
    marker = directory / "run_config.json"
    if marker.exists():
        if json.loads(marker.read_text(encoding="utf-8")) != config:
            raise ValueError("Paraphrase inputs or settings changed; use a new output directory")
    elif any(directory.glob("*.jsonl")):
        raise ValueError("Unversioned paraphrase checkpoints require a new output directory")
    else:
        directory.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return config


def stage_eval(a):
    pairs = load_pairs(a.pairs)
    if a.limit:
        pairs = pairs[:a.limit]
    model = a.model
    mdir = os.path.join(a.out, model.replace("/", "_"))
    bind_eval_config(mdir, pairs, a)
    k = key()
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
        text = p[arm]
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
    g.add_argument("--cases", default=CASES)
    for parser in (g, e):
        parser.add_argument("--pairs", default=PAIRS, help="Generated paraphrase input JSON path")
    e.add_argument("--out", default=OUT, help="New evaluation output directory")
    a = ap.parse_args()
    if a.workers < 1 or a.limit < 0 or (a.stage == "eval" and a.samples < 1):
        ap.error("Use positive workers/samples and a nonnegative limit")
    (stage_generate if a.stage == "generate" else stage_eval)(a)


if __name__ == "__main__":
    main()
