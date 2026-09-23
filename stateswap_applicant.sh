#!/bin/bash
#SBATCH --job-name=stateswap_applicant
#SBATCH --account=def-zhijing
#SBATCH --time=24:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --output=stateswap_applicant_%j.log
set -euo pipefail
ROOT=${SLURM_SUBMIT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
cd "$ROOT"
export PYTHONUNBUFFERED=1
: "${OPENROUTER_API_KEY:?Set OPENROUTER_API_KEY in the environment}"
MODEL=${1:?Usage: stateswap_applicant.sh MODEL_ID}
exec python experiments/stateswap_applicant_run.py --model "$MODEL" \
  --samples "${SAMPLES:-10}" --workers "${WORKERS:-60}" \
  --out "${OUT:-data/experiments/stateswap_applicant}"
