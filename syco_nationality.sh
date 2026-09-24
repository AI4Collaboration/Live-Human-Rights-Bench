#!/bin/bash
#SBATCH --job-name=syco_nat
#SBATCH --time=50:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --output=syco_nat_%j.log

# Nationality-role persuasion (summary-based) for one old model.
set -uo pipefail
export PYTHONUNBUFFERED=1
M="$1"
echo "=== syco_nat $M START $(date) ==="
cd -- "$(dirname -- "${BASH_SOURCE[0]}")" || exit 1
if [[ -n "${BENCHMARK_VENV:-}" ]]; then source "$BENCHMARK_VENV/bin/activate"; fi
# API credentials are read from environment variables or the local .env file.
if [[ -z "${OPENROUTER_API_KEY:-}" && -f .env ]]; then
  export OPENROUTER_API_KEY
  OPENROUTER_API_KEY="$(python -c "from dotenv import dotenv_values; print(dotenv_values('.env').get('OPENROUTER_API_KEY') or '')")"
fi
python experiments/syco_nationality_run.py --model "$M" --samples 3 --workers 40
echo "=== syco_nat $M DONE $(date) ==="
