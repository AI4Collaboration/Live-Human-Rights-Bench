#!/bin/bash
#SBATCH --job-name=para_eval
#SBATCH --account=def-zhijing
#SBATCH --time=50:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --output=para_eval_%j.log
set -uo pipefail
export PYTHONUNBUFFERED=1
M="$1"
echo "=== para EVAL $M START $(date) ==="
module load python/3.12 2>/dev/null || true
source /home/ariankh/legalllms/bin/activate
cd /scratch/ariankh/Legal-Sycophancy/shared-integration || { echo ABORT; exit 1; }
export OPENROUTER_API_KEY=$(grep '^OPENROUTER_API_KEY=' /scratch/ariankh/Legal-Sycophancy/Legal-Sycophancy/.env | cut -d= -f2-)
python experiments/paraphrase_run.py eval --model "$M" --samples 10 --workers 60
echo "=== para EVAL $M DONE $(date) ==="
