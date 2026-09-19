#!/bin/bash
#SBATCH --job-name=oldmodels
#SBATCH --account=def-zhijing
#SBATCH --time=50:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --output=oldmodels_%j.log

# Old-model run (gpt-4o-mini / gpt-4.1-mini): full-case baseline + summary arm +
# paraphrase + state-swap. NO sycophancy. Dedicated output dirs so nothing collides
# with the 6-model roster results.
set -uo pipefail
export PYTHONUNBUFFERED=1
export MLFLOW_TRACKING_URI=file:./mlruns
M="$1"
echo "=== oldmodels $M START $(date) on $(hostname) ==="
module load python/3.12 2>/dev/null || true
source /home/ariankh/legalllms/bin/activate
cd /scratch/ariankh/Legal-Sycophancy/shared-integration || { echo ABORT; exit 1; }
export OPENROUTER_API_KEY=$(grep '^OPENROUTER_API_KEY=' /scratch/ariankh/Legal-Sycophancy/Legal-Sycophancy/.env | cut -d= -f2-)
BASE="https://openrouter.ai/api/v1"

echo "--- full-case baseline $M $(date) ---"
python experiments/run_perturbation_fullcase.py --cases data/processed/echr_unified.json --model "$M" \
  --base-url "$BASE" --api-key-env OPENROUTER_API_KEY --summaries data/processed/summaries_dsv41flash.json \
  --rq baseline --samples 10 --workers 60 --output-dir data/experiments/unified_fullcase_oldmodels || echo "WARN baseline"
echo "--- summary arm (rq1) $M $(date) ---"
python experiments/run_perturbation_fullcase.py --cases data/processed/echr_unified.json --model "$M" \
  --base-url "$BASE" --api-key-env OPENROUTER_API_KEY --summaries data/processed/summaries_dsv41flash.json \
  --rq rq1 --samples 10 --workers 60 --output-dir data/experiments/unified_fullcase_oldmodels || echo "WARN rq1"

echo "--- paraphrase $M $(date) ---"
python experiments/paraphrase_run.py eval --model "$M" --samples 10 --workers 60 \
  --pairs data/processed/paraphrase_pairs.json --out data/experiments/paraphrase_oldmodels || echo "WARN paraphrase"

echo "--- state-swap $M $(date) ---"
python experiments/stateswap_summary_run.py --model "$M" --samples 10 --workers 60 \
  --out data/experiments/stateswap_oldmodels || echo "WARN stateswap"

echo "=== oldmodels $M DONE $(date) ==="
