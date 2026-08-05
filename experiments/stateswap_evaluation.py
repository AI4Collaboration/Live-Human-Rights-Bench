"""
State-swap model-side eval, with Anthropic prompt caching.

Scores case_text_rendered for all 4 arms across the roster (N samples, baseline
prompt, article from article_full). To make caching actually hit, the runner is
case-outside / samples-inside: for each (case, arm) unit it fires sample 0 first
to warm the cache, then the remaining samples read it, all inside Anthropic's
~5-minute window. cache_control sits on the case-text block only.

Input : data/processed/echr_stateswap.json  (build_stateswap_input.py)
Output: data/experiments/stateswap/<model>_stateswap_samples<N>.csv
"""
import argparse, asyncio, json, os, sys
from pathlib import Path

import aiohttp
import numpy as np
import pandas as pd
from dotenv import load_dotenv
load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lib.models import prepare_request
from lib.evaluation import extract_rating_from_response
from lib.prompts import (EVALUATION_SYSTEM_PROMPT, BASELINE_EVALUATION_TEMPLATE,
                         get_article_title)
from lib.metrics import calculate_accuracy

EVALUATORS = {
    # --- flagships ---
    "gpt-5.6":           {"model_id": "openai/gpt-5.6-sol"},
    "gpt-5.6-terra":     {"model_id": "openai/gpt-5.6-terra"},
    "gpt-5.6-luna":      {"model_id": "openai/gpt-5.6-luna"},
    "claude-opus-4.8":   {"model_id": "anthropic/claude-opus-4.8"},
    "gemini-3.5-flash":  {"model_id": "google/gemini-3.5-flash"},
    "deepseek-v4":       {"model_id": "deepseek/deepseek-v4-pro"},
    # --- size track ---
    "deepseek-v4-flash": {"model_id": "deepseek/deepseek-v4-flash"},
    "qwen3-8b":          {"model_id": "qwen/qwen3-8b"},
    "qwen3-32b":         {"model_id": "qwen/qwen3-32b"},
    "qwen3-235b":        {"model_id": "qwen/qwen3-235b-a22b"},
}

INPUT_PATH = REPO_ROOT / "data" / "processed" / "echr_stateswap.json"
OUTPUT_DIR = REPO_ROOT / "data" / "experiments" / "stateswap"
ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"


def prediction_from_rating(avg):
    if avg is None or (isinstance(avg, float) and np.isnan(avg)):
        return "failed"
    return "violation" if avg < 3 else "no_violation" if avg > 3 else "abstention"


def split_prompt(case_text, article):
    pre, post = BASELINE_EVALUATION_TEMPLATE.split("{case_text}")
    cached = pre + case_text
    return cached, post.format(article=article, article_title=get_article_title(article))


def build_messages(model_id, cached, uncached):
    ml = model_id.lower()
    if "claude" in ml:   # explicit prompt caching on the case-text block
        return [
            {"role": "system", "content": EVALUATION_SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": cached, "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": uncached},
            ]},
        ]
    if "gemini" in ml:   # gemini dislikes system role; fold in
        return [{"role": "user", "content": f"{EVALUATION_SYSTEM_PROMPT}\n\n{cached}{uncached}"}]
    return [   # others: identical prefix -> provider auto-caching (OpenAI/DeepSeek)
        {"role": "system", "content": EVALUATION_SYSTEM_PROMPT},
        {"role": "user", "content": cached + uncached},
    ]


def model_params(model_id):
    r = prepare_request("x", model_id, [], "k", True)
    return {k: r[k] for k in ("max_tokens", "max_completion_tokens",
                              "reasoning_effort", "temperature") if k in r}


async def one_call(session, key, model, messages, params, retries=3):
    body = {"model": model, "messages": messages, "usage": {"include": True}, **params}
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    for a in range(retries):
        try:
            async with session.post(ENDPOINT, json=body, headers=headers) as r:
                r.raise_for_status()
                d = await r.json()
                ch = (d.get("choices") or [{}])[0]
                content = (ch.get("message") or {}).get("content") or ""
                u = d.get("usage") or {}
                cached = ((u.get("prompt_tokens_details") or {}).get("cached_tokens")
                          or u.get("cache_read_input_tokens") or 0)
                if not content.strip():
                    raise ValueError("empty content")
                return content, int(u.get("prompt_tokens", 0) or 0), int(cached or 0), True
        except Exception:
            if a < retries - 1:
                await asyncio.sleep(2 ** a)
    # Exhausted retries. Returning a parseable body here would be indistinguishable
    # from a genuine abstention (extract_rating_from_response defaults to 3), so the
    # caller is told explicitly that this sample does not exist.
    return "", 0, 0, False


async def run_model(key, model_id, cases, n, max_conc):
    sem = asyncio.Semaphore(max_conc)
    params = model_params(model_id)
    timeout = aiohttp.ClientTimeout(total=180)
    stats = {"prompt": 0, "cached": 0, "calls": 0, "failed": 0}
    out = {}

    async def do_unit(idx, case):
        cached, uncached = split_prompt(case["full_case_text"], case["article"])
        msgs = build_messages(model_id, cached, uncached)
        async with sem:
            first = await one_call(session, key, model_id, msgs, params)   # warm cache
            rest = await asyncio.gather(*[one_call(session, key, model_id, msgs, params)
                                          for _ in range(n - 1)])
        calls = [first] + list(rest)
        # Only successful calls become ratings; a dead call is a missing sample,
        # not an abstention.
        ratings = [extract_rating_from_response(c) for c, _, _, ok in calls if ok]
        failed = sum(1 for *_, ok in calls if not ok)
        stats["prompt"] += sum(p for _, p, _, _ in calls)
        stats["cached"] += sum(r for _, _, r, _ in calls)
        stats["calls"] += len(calls)
        stats["failed"] += failed
        out[idx] = {"ratings": ratings, "failed": failed}

    async with aiohttp.ClientSession(timeout=timeout) as session:
        tasks = [asyncio.create_task(do_unit(i, c)) for i, c in enumerate(cases)]
        done = 0
        for t in asyncio.as_completed(tasks):
            await t
            done += 1
            if done % 50 == 0 or done == len(tasks):
                print(f"  {done}/{len(tasks)} cases")
    return out, stats


def evaluate(cases, name, cfg, key, n, max_conc):
    print(f"\n{'=' * 80}\nState-swap eval - {name} ({cfg['model_id']})")
    print(f"Units: {len(cases)}, Samples: {n}, Concurrent cases: {max_conc}\n{'=' * 80}")
    out, stats = asyncio.run(run_model(key, cfg["model_id"], cases, n, max_conc))

    rows = []
    for i, case in enumerate(cases):
        unit = out.get(i, {"ratings": [], "failed": n})
        srs, failed = unit["ratings"], unit["failed"]
        avg = float(np.mean(srs)) if srs else float("nan")
        is_violation = case["violation_label"] == "violation"
        rows.append({
            "swap_group_id": case["swap_group_id"], "item_id": case["item_id"],
            "arm": case["arm"], "article": case["article"], "respondent": case["respondent"],
            "violation_label": case["violation_label"], "avg_rating": avg,
            "prediction": prediction_from_rating(avg),
            "is_accurate": (calculate_accuracy(avg, is_violation) if srs else False),
            "num_abstentions": sum(1 for r in srs if r == 3),
            "num_samples": len(srs), "num_failed_calls": failed,
            "sample_ratings": str(srs),
        })
    df = pd.DataFrame(rows)
    hit = stats["cached"] / stats["prompt"] if stats["prompt"] else 0.0
    fail_rate = stats["failed"] / stats["calls"] if stats["calls"] else 0.0
    scored = int((df["num_samples"] > 0).sum())
    print(f"\n{name}: abstention "
          f"{df['num_abstentions'].sum() / max(1, df['num_samples'].sum()):.1%} | "
          f"cache hit {hit:.0%} ({stats['cached']:,}/{stats['prompt']:,} input tok)")
    print(f"{name}: failed calls {stats['failed']:,}/{stats['calls']:,} ({fail_rate:.2%}); "
          f"rows with no usable sample: {len(df) - scored}")
    return df, fail_rate


def main():
    ap = argparse.ArgumentParser(description="State-swap eval with prompt caching")
    ap.add_argument("--evaluator", choices=list(EVALUATORS.keys()))
    ap.add_argument("--all-evaluators", action="store_true")
    ap.add_argument("--num-samples", type=int, default=10)
    ap.add_argument("--max-conc", type=int, default=8, help="concurrent cases")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--input", type=Path, default=INPUT_PATH)
    ap.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    ap.add_argument("--max-fail-rate", type=float, default=0.02,
                    help="refuse to write results above this share of dead calls")
    args = ap.parse_args()

    if not args.all_evaluators and not args.evaluator:
        ap.error("Must specify --evaluator or --all-evaluators")
    to_run = list(EVALUATORS.keys()) if args.all_evaluators else [args.evaluator]

    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        print("ERROR: OPENROUTER_API_KEY not set"); sys.exit(1)
    if not args.input.exists():
        print(f"ERROR: {args.input} not found. Run scripts/build_stateswap_input.py"); sys.exit(1)
    cases = json.load(open(args.input))
    print(f"Loaded {len(cases)} state-swap rows")
    if args.limit:
        cases = cases[:args.limit]
        print(f"[--limit] {len(cases)} rows")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    degraded = []
    for name in to_run:
        df, fail_rate = evaluate(cases, name, EVALUATORS[name], key,
                                 args.num_samples, args.max_conc)
        if fail_rate > args.max_fail_rate:
            # A quiet run with dead calls looks exactly like a run with no effect,
            # which is the conclusion this experiment is trying to establish.
            print(f"REFUSING to write {name}: failure rate {fail_rate:.2%} exceeds "
                  f"--max-fail-rate {args.max_fail_rate:.2%}. Re-run this model.")
            degraded.append(name)
            continue
        out = args.output_dir / f"{name}_stateswap_samples{args.num_samples}.csv"
        df.to_csv(out, index=False)
        print(f"Saved {out}")
    if degraded:
        print(f"\nState-swap evaluation finished with {len(degraded)} unusable "
              f"model run(s): {', '.join(degraded)}")
        sys.exit(1)
    print("\nState-swap evaluation complete.")


if __name__ == "__main__":
    main()
