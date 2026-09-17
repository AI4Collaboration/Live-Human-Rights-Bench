#!/bin/bash
#SBATCH --job-name=para_gen
#SBATCH --account=def-zhijing
#SBATCH --time=50:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --output=para_gen_%j.log
set -uo pipefail
export PYTHONUNBUFFERED=1
echo "=== para GEN START $(date) ==="
module load python/3.12 2>/dev/null || true
source /home/ariankh/legalllms/bin/activate
cd /scratch/ariankh/Legal-Sycophancy/shared-integration || { echo ABORT; exit 1; }
export OPENROUTER_API_KEY=$(grep '^OPENROUTER_API_KEY=' /scratch/ariankh/Legal-Sycophancy/Legal-Sycophancy/.env | cut -d= -f2-)
python experiments/paraphrase_run.py generate --paraphraser openai/gpt-5.6-sol --workers 40
echo "=== para GEN DONE $(date) ==="
