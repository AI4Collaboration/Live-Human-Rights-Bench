#!/bin/bash
#SBATCH --job-name=stateswap
#SBATCH --account=def-zhijing
#SBATCH --time=24:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --output=stateswap_%j.log
set -uo pipefail
export PYTHONUNBUFFERED=1
M="$1"
echo "=== stateswap $M START $(date) ==="
module load python/3.12 2>/dev/null || true
source /home/ariankh/legalllms/bin/activate
cd /scratch/ariankh/Legal-Sycophancy/shared-integration || { echo ABORT; exit 1; }
export OPENROUTER_API_KEY=$(grep '^OPENROUTER_API_KEY=' /scratch/ariankh/Legal-Sycophancy/Legal-Sycophancy/.env | cut -d= -f2-)
python experiments/stateswap_summary_run.py --model "$M" --samples 10 --workers 60
echo "=== stateswap $M DONE $(date) ==="
