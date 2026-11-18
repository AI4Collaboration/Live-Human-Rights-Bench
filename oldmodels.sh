#!/bin/bash
#SBATCH --job-name=oldmodels
#SBATCH --time=50:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --output=oldmodels_%j.log

# Earlier-model evaluation: full-case baseline, summary, paraphrase and Country Swap.
# Set OUT to a fresh directory for each experiment.
set -euo pipefail
export PYTHONUNBUFFERED=1
export MLFLOW_TRACKING_URI=${MLFLOW_TRACKING_URI:-file:./mlruns}
MODEL=${1:?Usage: oldmodels.sh MODEL_ID}
ROOT=${SLURM_SUBMIT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
cd "$ROOT"
if [[ -n "${BENCHMARK_VENV:-}" ]]; then source "$BENCHMARK_VENV/bin/activate"; fi
: "${OPENROUTER_API_KEY:?Set OPENROUTER_API_KEY in the environment}"
PYTHON=${PYTHON:-python}
OUT=${OUT:-data/experiments/earlier_models_new}
SAMPLES=${SAMPLES:-10}
WORKERS=${WORKERS:-60}

echo "Full-case baseline and summary: $MODEL"
"$PYTHON" experiments/run_perturbation_fullcase.py \
  --cases data/processed/echr_unified.json --model "$MODEL" \
  --base-url https://openrouter.ai/api/v1 --api-key-env OPENROUTER_API_KEY \
  --summaries data/processed/summaries_dsv41flash.json \
  --rq all --samples "$SAMPLES" --workers "$WORKERS" --output-dir "$OUT/fullcase"

echo "Paraphrase: $MODEL"
"$PYTHON" experiments/paraphrase_run.py eval --model "$MODEL" \
  --samples "$SAMPLES" --workers "$WORKERS" \
  --pairs data/processed/paraphrase_pairs.json --out "$OUT/paraphrase"

echo "Country Swap: $MODEL"
"$PYTHON" experiments/stateswap_summary_run.py --model "$MODEL" \
  --samples "$SAMPLES" --workers "$WORKERS" --out "$OUT/country_swap"

echo "Completed: $MODEL"
