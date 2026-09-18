#!/bin/bash
#SBATCH --job-name=para_eval
#SBATCH --account=def-zhijing
#SBATCH --time=50:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --output=para_eval_%j.log

set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$ROOT"
export PYTHONUNBUFFERED=1
: "${OPENROUTER_API_KEY:?Set OPENROUTER_API_KEY in the environment}"
MODEL=${1:?Usage: paraphrase_eval.sh MODEL_ID}
exec python experiments/paraphrase_run.py eval --model "$MODEL" \
  --pairs "${PAIRS:-data/processed/paraphrase_pairs_new.json}" \
  --out "${OUT:-data/experiments/paraphrase_new}" --samples 10 --workers "${WORKERS:-60}"
