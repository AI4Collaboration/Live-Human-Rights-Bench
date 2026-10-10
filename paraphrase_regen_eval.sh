#!/bin/bash
#SBATCH --job-name=para_regen
#SBATCH --account=def-zhijing
#SBATCH --time=6:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --output=para_regen_%j.log
set -euo pipefail
ROOT=${SLURM_SUBMIT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
cd "$ROOT"
export PYTHONUNBUFFERED=1
: "${OPENROUTER_API_KEY:?Set OPENROUTER_API_KEY}"

PAIRS=data/processed/paraphrase_pairs_regen_cut.json
REGEN_OUT=data/experiments/paraphrase_regen
MODELS="anthropic/claude-opus-4.6 openai/gpt-5.6-sol deepseek/deepseek-v4-pro deepseek/deepseek-v4-flash qwen/qwen3-235b-a22b qwen/qwen3-32b"

echo "=== STEP 1: re-score the 26 regenerated targets on 6 models ==="
for m in $MODELS; do
  echo "-- eval $m"
  python experiments/paraphrase_run.py eval --model "$m" --pairs "$PAIRS" --out "$REGEN_OUT" --samples 10 --workers 40
done

echo "=== STEP 2: swap the 26 targets' rows into the main paraphrase results ==="
python - <<'PY'
import json, os
pairs = json.load(open("data/processed/paraphrase_pairs_regen_cut.json"))
keys = {(p["item_id"], p["article"]) for p in pairs}
base = "data/experiments/paraphrase"
regen = "data/experiments/paraphrase_regen"
for d in sorted(os.listdir(regen)):
    mp = os.path.join(base, d, "paraphrase_results.jsonl")
    rp = os.path.join(regen, d, "paraphrase_results.jsonl")
    if not os.path.exists(mp):
        print("  SKIP (no main results):", d); continue
    main = [json.loads(l) for l in open(mp) if l.strip()]
    new = [json.loads(l) for l in open(rp) if l.strip()]
    kept = [r for r in main if (r["item_id"], r["article"]) not in keys]
    os.replace(mp, mp + ".preregen.bak")
    with open(mp, "w", encoding="utf-8", newline="\n") as h:
        for r in kept + new:
            h.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  {d}: main {len(main)} -> {len(kept)} kept + {len(new)} regen = {len(kept)+len(new)}")
PY

echo "=== STEP 3: merge regenerated texts into the main paraphrase text file ==="
python quality_control/paraphrase/regen/merge_texts.py \
  data/processed/paraphrase_texts.jsonl.gz \
  data/processed/paraphrase_texts_regen_cut.jsonl.gz \
  data/processed/paraphrase_texts_merged.jsonl.gz \
  data/processed/paraphrase_texts_regen_subset.jsonl.gz
cp data/processed/paraphrase_texts.jsonl.gz data/processed/paraphrase_texts.jsonl.gz.preregen.bak
mv data/processed/paraphrase_texts_merged.jsonl.gz data/processed/paraphrase_texts.jsonl.gz
echo "=== ALL DONE ==="
