#!/bin/bash
#SBATCH --job-name=syco_par
#SBATCH --time=50:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --output=syco_par_%j.log

set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$ROOT"
export PYTHONUNBUFFERED=1
: "${OPENROUTER_API_KEY:?Set OPENROUTER_API_KEY in the environment}"
MODEL=${1:?Usage: syco_par.sh MODEL_ID}
SAFE=${MODEL//\//_}
exec python experiments/syco_run.py \
  --cases data/processed/echr_unified.json --summaries data/processed/summaries_dsv41flash.json \
  --out "${OUT:-data/experiments/syco_models_new}/$SAFE" \
  --targets "$MODEL" --turns 3 --workers "${WORKERS:-24}"
