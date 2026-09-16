#!/usr/bin/env python3
"""Build the extractive control arm: summaries that are verbatim source paragraphs.

Writes the canonical single-summary file shape, so every runner consumes it
unchanged -- the arm is run by pointing --summaries at this file instead.

    python scripts/build_extractive.py \
      --cases data/processed/echr_unified.json \
      --summarizer deepseek/deepseek-v4.1-flash --api-key-env OPENROUTER_API_KEY \
      --out data/processed/summaries_extractive_dsv41flash.json

What it buys: the abstractive arm confounds omission with invention. Here the model
may only choose source spans, so any effect is omission alone, and the omission is the
exact list of spans left out rather than something an entailment judge estimated.
The selector keeps every span it considers necessary; no arbitrary word budget is
imposed.
"""

import argparse, json, os, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed

from openai import OpenAI

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "experiments"))
from checkpoint import Checkpoint          # noqa: E402
from scoring import MAX_CASE_CHARS         # noqa: E402
from input_gate import case_input, guard_candidate_output, manifest  # noqa: E402
from extractive import (SPAN_SELECT_TEMPLATE, assemble_units, is_verbatim,  # noqa: E402
                        parse_selection, source_units, selection_record,
                        SELECTION_SCHEMA)

ATTEMPTS = 3


def preflight(cases):
    """Expose format exclusions before paying for a partially matched cohort."""
    problems, eligible = [], 0
    for case in cases:
        units = source_units(case["text"])
        compact = lambda text: "".join(text.split())
        reason = ("empty_source" if not units else
                  "source_partition_mismatch" if compact("".join(u["text"] for u in units)) != compact(case["text"]) else None)
        if reason:
            problems.append({"item_id": case["item_id"], "reason": reason})
        else:
            eligible += 1
    return {"judgments": len(cases), "eligible": eligible, "blocked": len(problems), "problems": problems}


def extract(client, model, case, max_tokens,
            reasoning_effort, temperature):
    units = source_units(case["text"])
    if not units:
        return None, "ERROR: empty source", None, {"prompt": 0, "completion": 0}
    numbered = "\n\n".join(f"[{u['id']}] {u['text']}" for u in units)
    prompt = SPAN_SELECT_TEMPLATE.format(case_name=case["case_name"], numbered=numbered)
    valid = {u["id"] for u in units}
    usage = {"prompt": 0, "completion": 0}
    last = "ERROR: no attempt made"
    for attempt in range(ATTEMPTS):
        try:
            request = {
                "model": model, "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature, "max_tokens": max_tokens,
            }
            if reasoning_effort != "provider_default":
                request["extra_body"] = {"reasoning": {"effort": reasoning_effort}}
            resp = client.chat.completions.create(
                **request)
            if resp.usage:
                usage["prompt"] += resp.usage.prompt_tokens or 0
                usage["completion"] += resp.usage.completion_tokens or 0
            chosen = parse_selection((resp.choices[0].message.content or ""), valid)
            if not chosen:
                last = "ERROR: no valid paragraph numbers in reply"
                continue
            text = assemble_units(units, chosen)
            # The guarantee the whole arm rests on, checked rather than assumed.
            if not is_verbatim(text, case["text"]):
                last = "ERROR: assembled extract is not verbatim"
                continue
            # The complete source has already passed its identity gate. A lexical
            # outcome filter would wrongly reject permitted domestic findings.
            return text, None, selection_record(units, chosen), usage
        except Exception as e:
            last = f"ERROR: {e}"
            time.sleep(2 * (attempt + 1))
    return None, last, None, usage


def main():
    p = argparse.ArgumentParser(description="Build the extractive control summaries")
    p.add_argument("--cases", required=True)
    p.add_argument("--summarizer", required=True)
    p.add_argument("--base-url", default="https://openrouter.ai/api/v1")
    p.add_argument("--api-key-env", default="OPENROUTER_API_KEY")
    p.add_argument("--out", required=True)
    p.add_argument("--workers", type=int, default=20)
    p.add_argument("--max-tokens", type=int, default=4000)
    p.add_argument("--reasoning-effort", default="none",
                   choices=("provider_default", "none", "minimal", "low", "medium", "high"),
                   help="selector reasoning effort; none is sufficient for span selection")
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--limit", type=int)
    p.add_argument("--no-resume", action="store_true")
    p.add_argument("--check-only", action="store_true", help="offline source-format preflight; no model calls")
    args = p.parse_args()
    guard_candidate_output(args.out)

    with open(args.cases, encoding="utf-8") as handle:
        instances = json.load(handle)
    judgments, article_of = {}, {}
    for c in instances:
        article_of.setdefault(c["item_id"], set()).add(c.get("article_full") or c["article"])
        if c["item_id"] in judgments:
            continue
        text = case_input(c)
        judgments[c["item_id"]] = {"item_id": c["item_id"], "case_name": c["case_name"],
                                   "text": text[:MAX_CASE_CHARS]}
    article_of = {k: "; ".join(sorted(v)) for k, v in article_of.items()}
    cases = list(judgments.values())
    if args.limit:
        cases = cases[:args.limit]
    checked = preflight(cases)
    if args.check_only:
        print(json.dumps(checked, indent=2))
        return
    if checked["blocked"]:
        sys.exit(f"Extractive format preflight blocked: {checked['eligible']}/{checked['judgments']} judgments are compatible; "
                 "resolve paragraph segmentation first. No selector calls made. Use --check-only for IDs.")
    key = os.environ.get(args.api_key_env, "")
    if not key:
        sys.exit(f"ERROR: set {args.api_key_env}")

    print(f"Selector: {args.summarizer}   judgments: {len(cases)}   "
          "one unbounded extract per judgment\n")

    ckpt = Checkpoint(args.out + ".jsonl", enabled=not args.no_resume)
    dataset_id = manifest()["dataset_id"]
    for row in ckpt.rows():
        expected = judgments.get(row["item_id"])
        if (row.get("version") != 0 or expected is None
                or row.get("dataset_id") != dataset_id
                or row.get("source_characters") != len(expected["text"])
                or row.get("summarizer") != args.summarizer
                or row.get("selection_schema") != SELECTION_SCHEMA
                or row.get("reasoning_effort") != args.reasoning_effort
                or row.get("temperature") != args.temperature
                or row.get("provisions") != article_of[row["item_id"]]):
            ckpt.close()
            sys.exit("Stale or multi-version extract checkpoint; choose a new output path")
    if ckpt.resumed:
        print(f"Resuming: {ckpt.resumed} already recorded\n")
    client = OpenAI(base_url=args.base_url, api_key=key)

    units = [c for c in cases if not ckpt.done(Checkpoint.key("extract", c["item_id"], "", 0))]
    done = failed = 0
    tot = {"prompt": 0, "completion": 0}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(extract, client, args.summarizer, c, args.max_tokens,
                            args.reasoning_effort, args.temperature): c
                for c in units}
        for fut in as_completed(futs):
            case = futs[fut]
            text, err, drop, usage = fut.result()
            tot["prompt"] += usage["prompt"]; tot["completion"] += usage["completion"]
            done += 1
            if text:
                ckpt.record(Checkpoint.key("extract", case["item_id"], "", 0),
                            {"item_id": case["item_id"], "case_name": case["case_name"],
                             "version": 0, "summary": text, **drop,
                             "selection_schema": SELECTION_SCHEMA,
                             "provisions": article_of[case["item_id"]], "summarizer": args.summarizer,
                             "reasoning_effort": args.reasoning_effort,
                             "temperature": args.temperature,
                             "dataset_id": dataset_id,
                             "source_characters": len(case["text"])})
            else:
                failed += 1
                print(f"\n  {case['case_name'][:40]}: {err[:90]}")
            print(f"\r  {done}/{len(units)} | failed {failed}", end="", flush=True)
    print()
    ckpt.close()

    requested = {c["item_id"] for c in cases}
    by_case = {r["item_id"]: r for r in ckpt.rows() if r["item_id"] in requested}
    summaries = {k: [r["summary"]] for k, r in by_case.items()}
    selections = {k: {field: r[field] for field in
                  ("selected_units", "omitted_units", "selected_spans", "selected_words")}
                  for k, r in by_case.items()}
    complete = len(summaries)

    json.dump({"dataset_id": dataset_id, "summarizer": args.summarizer, "versions": 1,
               "mode": "extractive",
               "selection_rule": "all source spans material to any alleged violation, with no length constraint",
               "reasoning_effort": args.reasoning_effort, "temperature": args.temperature,
               "n_judgments": len(cases), "n_complete": complete,
               "prompt_tokens": tot["prompt"], "completion_tokens": tot["completion"],
               "source_characters": {c["item_id"]: len(c["text"]) for c in cases},
               "selection_schema": SELECTION_SCHEMA, "selections": selections,
               "provisions": article_of, "summaries": summaries},
              open(args.out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"\nWrote {args.out}")
    print(f"  {complete}/{len(cases)} judgments complete")
    print(f"  tokens: {tot['prompt']:,} in, {tot['completion']:,} out")


if __name__ == "__main__":
    main()
