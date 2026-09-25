#!/bin/bash
#SBATCH --job-name=syco_cot
#SBATCH --account=def-zhijing
#SBATCH --time=24:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --output=syco_cot_%j.log
set -euo pipefail
ROOT=${SLURM_SUBMIT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
cd "$ROOT"
export PYTHONUNBUFFERED=1
# openrouter backend needs OPENROUTER_API_KEY; bedrock backend needs AWS_BEARER_TOKEN_BEDROCK + AWS_REGION.
BACKEND=${BACKEND:-openrouter}
# bedrock needs boto3; pin PYTHON to a interpreter that has it (default: plain python).
PYTHON=${PYTHON:-python}
MODEL=${1:?Usage: syco_cot.sh MODEL_ID  (env: BACKEND, CONDITIONS, OUT, LIMIT, WORKERS, PYTHON)}
exec "$PYTHON" experiments/syco_cot_run.py --backend "$BACKEND" --model "$MODEL" \
  --workers "${WORKERS:-16}" --limit "${LIMIT:-0}" \
  ${CONDITIONS:+--conditions $CONDITIONS} \
  ${ARMS:+--arms $ARMS} \
  --out "${OUT:-data/experiments/syco_cot}"
