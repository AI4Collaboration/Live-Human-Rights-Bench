#!/bin/bash
#SBATCH --job-name=qwen_par
#SBATCH --time=24:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --output=qwen_par_%j.log

set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$ROOT"
export PYTHONUNBUFFERED=1
: "${OPENROUTER_API_KEY:?Set OPENROUTER_API_KEY in the environment}"
MODEL=${1:?Usage: model_par.sh MODEL_ID}
exec python experiments/run_perturbation_fullcase.py \
  --cases data/processed/echr_unified.json --summaries data/processed/summaries_dsv41flash.json \
  --model "$MODEL" --base-url https://openrouter.ai/api/v1 --api-key-env OPENROUTER_API_KEY \
  --rq all --samples 10 --workers "${WORKERS:-20}" --output-dir "${OUT:-data/experiments/fullcase_new}"
