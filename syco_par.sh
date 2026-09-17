#!/bin/bash
#SBATCH --job-name=syco_par
#SBATCH --account=def-zhijing
#SBATCH --time=50:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --output=syco_par_%j.log

# Sycophancy for ONE target model (parallel per-target speedup). Own output dir so the
# per-target jsonl checkpoints never collide. Challenger GPT-5.4-nano, T=3, full grid.
set -uo pipefail
export PYTHONUNBUFFERED=1
M="$1"
echo "=== syco $M START $(date) on $(hostname) ==="
module load python/3.12 2>/dev/null || true
source /home/ariankh/legalllms/bin/activate
cd /scratch/ariankh/Legal-Sycophancy/shared-integration || { echo ABORT; exit 1; }
export OPENROUTER_API_KEY=$(grep '^OPENROUTER_API_KEY=' /scratch/ariankh/Legal-Sycophancy/Legal-Sycophancy/.env | cut -d= -f2-)
SAFE=$(echo "$M" | tr '/' '_')
python experiments/syco_run.py --cases data/processed/echr_unified.json \
  --summaries data/processed/summaries_dsv41flash.json \
  --out "data/experiments/syco_full_par/$SAFE" \
  --targets "$M" --turns 3 --workers 60
echo "=== syco $M DONE $(date) ==="
