#!/bin/bash
#SBATCH --job-name=qwen_par
#SBATCH --account=def-zhijing
#SBATCH --time=24:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --output=qwen_par_%j.log

# Run ONE model (baseline then rq1) in parallel with the main job, into an isolated
# output dir so there is no checkpoint collision. Keep this year-balanced pool
# separate from historical full_scale runs.
set -uo pipefail
export PYTHONUNBUFFERED=1
export MLFLOW_TRACKING_URI=file:./mlruns
M="$1"
echo "=== $M START $(date) on $(hostname) ==="
module load python/3.12 2>/dev/null || true
source /home/ariankh/legalllms/bin/activate
cd /scratch/ariankh/Legal-Sycophancy/shared-integration || { echo ABORT; exit 1; }
export OPENROUTER_API_KEY=$(grep '^OPENROUTER_API_KEY=' /scratch/ariankh/Legal-Sycophancy/Legal-Sycophancy/.env | cut -d= -f2-)
OUT=${OUT:-data/experiments/unified_dsv41flash_par}
python experiments/run_perturbation_openai.py --cases data/processed/echr_unified.json --model "$M" \
  --base-url https://openrouter.ai/api/v1 --api-key-env OPENROUTER_API_KEY \
  --summaries data/processed/summaries_dsv41flash.json --rq baseline --samples 10 \
  --workers 40 --output-dir "$OUT" || { echo "WARN baseline $M"; exit 1; }
python experiments/run_perturbation_openai.py --cases data/processed/echr_unified.json --model "$M" \
  --base-url https://openrouter.ai/api/v1 --api-key-env OPENROUTER_API_KEY \
  --summaries data/processed/summaries_dsv41flash.json --rq rq1 --samples 10 \
  --workers 40 --output-dir "$OUT" || echo "WARN rq1 $M"
echo "=== $M DONE $(date) ==="
