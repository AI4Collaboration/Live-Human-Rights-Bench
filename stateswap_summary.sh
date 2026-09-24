#!/bin/bash
#SBATCH --job-name=stateswap
#SBATCH --time=24:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --output=stateswap_%j.log
set -euo pipefail
ROOT=${SLURM_SUBMIT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
cd "$ROOT"
export PYTHONUNBUFFERED=1
: "${OPENROUTER_API_KEY:?Set OPENROUTER_API_KEY in the environment}"
MODEL=${1:?Usage: stateswap_summary.sh MODEL_ID}
exec python experiments/stateswap_summary_run.py --model "$MODEL" \
  --samples 10 --workers "${WORKERS:-60}" --targets "${TARGETS:-us}" \
  --out "${OUT:-data/experiments/stateswap_summary_new}"
