#!/bin/bash
#SBATCH --job-name=resummarize_rescore
#SBATCH --account=def-zhijing
#SBATCH --time=24:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --output=resummarize_rescore_%j.log

# Rebuild DeepSeek v4.1 Flash summaries on the selected year-balanced evaluation
# set, then re-score baseline and the summary arm (rq1) for all 8 models.
set -uo pipefail
OUT=${OUT:-data/experiments/unified_dsv41flash_rescore}
export PYTHONUNBUFFERED=1
export MLFLOW_TRACKING_URI=file:./mlruns
echo "=== START $(date) on $(hostname) ==="
module load python/3.12 2>/dev/null || true
source /home/ariankh/legalllms/bin/activate
cd /scratch/ariankh/Legal-Sycophancy/shared-integration || { echo "ABORT: repo not found"; exit 1; }
export OPENROUTER_API_KEY=$(grep '^OPENROUTER_API_KEY=' /scratch/ariankh/Legal-Sycophancy/Legal-Sycophancy/.env | cut -d= -f2-)

python - <<'PY'
import urllib.request, sys
try: urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=15); print("internet OK")
except Exception as e: print("NO INTERNET:", e); sys.exit(1)
PY
[ $? -ne 0 ] && { echo "ABORT: no internet"; exit 1; }

echo "=== STEP 1 build deepseek-v4.1-flash summaries $(date) ==="
python scripts/build_summaries.py \
  --cases data/processed/echr_unified.json \
  --summarizer deepseek/deepseek-v4.1-flash \
  --base-url https://openrouter.ai/api/v1 \
  --api-key-env OPENROUTER_API_KEY \
  --out data/processed/summaries_dsv41flash.json
[ -s data/processed/summaries_dsv41flash.json ] || { echo "ABORT: summaries not built"; exit 1; }

echo "=== STEP 2 baseline then rq1 for 8 models $(date) ==="
for M in openai/gpt-5.6-sol anthropic/claude-opus-4.8 google/gemini-3.5-flash \
         deepseek/deepseek-v4-pro deepseek/deepseek-v4-flash \
         qwen/qwen3-8b qwen/qwen3-32b qwen/qwen3-235b-a22b; do
  echo "--- $M baseline $(date) ---"
  python experiments/run_perturbation_openai.py \
    --cases data/processed/echr_unified.json --model "$M" \
    --base-url https://openrouter.ai/api/v1 --api-key-env OPENROUTER_API_KEY \
    --summaries data/processed/summaries_dsv41flash.json \
    --rq baseline --samples 10 --output-dir "$OUT" || { echo "WARN: $M baseline failed, skipping rq1"; continue; }
  echo "--- $M rq1 $(date) ---"
  python experiments/run_perturbation_openai.py \
    --cases data/processed/echr_unified.json --model "$M" \
    --base-url https://openrouter.ai/api/v1 --api-key-env OPENROUTER_API_KEY \
    --summaries data/processed/summaries_dsv41flash.json \
    --rq rq1 --samples 10 --output-dir "$OUT" || echo "WARN: $M rq1 non-zero exit"
done
echo "=== DONE $(date) ==="
