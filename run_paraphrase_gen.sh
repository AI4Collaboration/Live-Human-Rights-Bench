#!/bin/bash
#SBATCH --job-name=para_gen
#SBATCH --account=def-zhijing
#SBATCH --time=50:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --output=para_gen_%j.log

set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$ROOT"
export PYTHONUNBUFFERED=1
: "${OPENROUTER_API_KEY:?Set OPENROUTER_API_KEY in the environment}"
exec python experiments/paraphrase_run.py generate \
  --pairs "${PAIRS:-data/processed/paraphrase_pairs_new.json}" \
  --paraphraser openai/gpt-5.6-sol --workers "${WORKERS:-40}"
