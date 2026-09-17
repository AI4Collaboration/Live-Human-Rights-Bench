#!/bin/bash
#SBATCH --job-name=summary_6models
#SBATCH --account=def-zhijing
#SBATCH --time=24:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --output=summary_6models_%j.log

# Rerun baseline + summary arm (rq1) on the FINAL leak-checked corpus for the agreed
# 6-model roster (Gemini and Qwen3-8B dropped, Opus 4.8 -> 4.6). Uses the existing
# clean DeepSeek v4.1-flash summaries (do NOT rebuild). Fresh output dir; results are
# force-added at commit time because data/experiments is gitignored.
set -uo pipefail
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

CASES=data/processed/echr_unified.json
SUMMARIES=data/processed/summaries_dsv41flash.json
OUT=data/experiments/unified_dsv41flash
echo "=== baseline then rq1 for 6 models -> $OUT $(date) ==="
for M in openai/gpt-5.6-sol anthropic/claude-opus-4.6 \
         deepseek/deepseek-v4-pro deepseek/deepseek-v4-flash \
         qwen/qwen3-32b qwen/qwen3-235b-a22b; do
  echo "--- $M baseline $(date) ---"
  python experiments/run_perturbation_openai.py --cases "$CASES" --model "$M" \
    --base-url https://openrouter.ai/api/v1 --api-key-env OPENROUTER_API_KEY \
    --summaries "$SUMMARIES" --rq baseline --samples 10 --workers 40 --output-dir "$OUT" \
    || { echo "WARN: $M baseline failed, skipping rq1"; continue; }
  echo "--- $M rq1 $(date) ---"
  python experiments/run_perturbation_openai.py --cases "$CASES" --model "$M" \
    --base-url https://openrouter.ai/api/v1 --api-key-env OPENROUTER_API_KEY \
    --summaries "$SUMMARIES" --rq rq1 --samples 10 --workers 40 --output-dir "$OUT" \
    || echo "WARN: $M rq1 non-zero exit"
done
echo "=== DONE $(date) ==="
