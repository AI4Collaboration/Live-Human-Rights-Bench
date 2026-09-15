#!/usr/bin/env python3
"""Read-only OpenRouter cost scenarios for the complete perturbation rescore.

This makes no completion calls. Tokenization is a cl100k proxy; provider usage,
reasoning, retries and cache discounts determine the actual bill.
"""
import argparse
import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def estimate(family, samples, encoding):
    catalog = json.load(urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=30))
    models = {m["id"]: m for m in catalog["data"]}
    cases = json.loads((ROOT / "data/processed/echr_unified.json").read_text(encoding="utf-8"))
    summaries = json.loads((ROOT / "data/processed/summaries_dsv41flash.json").read_text(encoding="utf-8"))["summaries"]
    constants = {}
    tree = ast.parse((ROOT / "experiments/run_perturbation_openai.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                constants[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                pass
    token_count = lambda text: len(encoding.encode(text))
    total_input = 0
    for case in cases:
        fields = dict(article=case["article"], article_title=constants["ARTICLE_TITLES"].get(case["article"], f"Article {case['article']}"))
        full = constants["PREDICTIVE_TEMPLATE"].format(case_text=case["full_case_text_no_verdict"][:50000], **fields)
        summary = constants["PREDICTIVE_TEMPLATE"].format(case_text=summaries[case["item_id"]][0], **fields)
        factual = constants["FACTUAL_TEMPLATE"].format(case_text=summaries[case["item_id"]][0], **fields)
        system = token_count(constants["SYSTEM_PROMPT"])
        # Baseline, RQ1, three RQ2 frames, RQ3 initial and follow-up.
        total_input += (3 * token_count(full) + 3 * token_count(summary) + token_count(factual)
                        + token_count(constants["RECONSIDERATION_PROMPT"]) + 7 * system + 7 * 16 + 4)
    calls = len(cases) * 7 * samples
    rows = []
    for model in family["models"]:
        if model not in models:
            raise ValueError(f"Model unavailable: {model}")
        pricing = models[model]["pricing"]
        input_cost = total_input * samples * float(pricing["prompt"])
        row = {"model": model, "calls_before_retries": calls,
               "input_usd_per_million": float(pricing["prompt"]) * 1e6,
               "output_usd_per_million": float(pricing["completion"]) * 1e6}
        for output in (1000, 4000, 8000):
            row[f"usd_at_{output}_output_tokens_per_call"] = round(input_cost + calls * output * float(pricing["completion"]), 2)
        rows.append(row)
    return {"checked_at": datetime.now(timezone.utc).isoformat(), "source": "https://openrouter.ai/api/v1/models",
            "samples": samples, "instances": len(cases), "summary_draws": 1,
            "calls_before_retries": calls * len(rows), "models": rows,
            "total_usd_scenarios": {str(n): round(sum(r[f"usd_at_{n}_output_tokens_per_call"] for r in rows), 2) for n in (1000, 4000, 8000)},
            "note": "Scenarios, not a quote or spending cap. Excludes retries, cache discounts, provider-tokenizer differences and separate faithfulness calls."}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--family", type=Path, default=ROOT / "configs/perturbation_analysis.json")
    p.add_argument("--samples", type=int, required=True)
    args = p.parse_args()
    if args.samples < 1:
        p.error("--samples must be positive")
    import tiktoken
    print(json.dumps(estimate(json.loads(args.family.read_text(encoding="utf-8")), args.samples,
                              tiktoken.get_encoding("cl100k_base")), indent=2))


if __name__ == "__main__":
    main()
