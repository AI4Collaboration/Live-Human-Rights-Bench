#!/bin/bash
#SBATCH --job-name=syco_nat
#SBATCH --time=50:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --output=syco_nat_%j.log

# Nationality cues in adversarial opinions, using shared summaries.
set -euo pipefail
export PYTHONUNBUFFERED=1
MODEL=${1:?Usage: syco_nationality.sh MODEL_ID}
ROOT=${SLURM_SUBMIT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
cd "$ROOT"
if [[ -n "${BENCHMARK_VENV:-}" ]]; then source "$BENCHMARK_VENV/bin/activate"; fi
: "${OPENROUTER_API_KEY:?Set OPENROUTER_API_KEY in the environment}"
exec "${PYTHON:-python}" experiments/syco_nationality_run.py --model "$MODEL" \
  --samples "${SAMPLES:-3}" --workers "${WORKERS:-40}" \
  --out "${OUT:-data/experiments/syco_nationality_new}"
