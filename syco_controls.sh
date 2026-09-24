#!/bin/bash
#SBATCH --job-name=syco_controls
#SBATCH --time=24:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --output=syco_controls_%j.log
set -euo pipefail
ROOT=${SLURM_SUBMIT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
cd "$ROOT"
export PYTHONUNBUFFERED=1
: "${OPENROUTER_API_KEY:?Set OPENROUTER_API_KEY in the environment}"
MODEL=${1:?Usage: syco_controls.sh MODEL_ID}
exec python experiments/syco_controls_run.py --model "$MODEL" \
  --turns "${TURNS:-3}" --trajectories "${TRAJ:-1}" --workers "${WORKERS:-40}" \
  --out "${OUT:-data/experiments/syco_controls}"
