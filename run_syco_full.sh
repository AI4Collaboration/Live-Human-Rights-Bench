#!/bin/bash
#SBATCH --job-name=syco_full
#SBATCH --account=def-zhijing
#SBATCH --time=65:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --output=syco_full_%j.log

# Full adversarial-opinion run: 6 targets x GPT-5.4-nano challenger, T=3, static+adaptive,
# full condition grid, all 1000 cases, on the DeepSeek v4.1-flash summaries. Checkpointed.
set -uo pipefail
export PYTHONUNBUFFERED=1
echo "=== START $(date) on $(hostname) ==="
module load python/3.12 2>/dev/null || true
source /home/ariankh/legalllms/bin/activate
cd /scratch/ariankh/Legal-Sycophancy/shared-integration || { echo ABORT; exit 1; }
export OPENROUTER_API_KEY=$(grep '^OPENROUTER_API_KEY=' /scratch/ariankh/Legal-Sycophancy/Legal-Sycophancy/.env | cut -d= -f2-)
python - <<'PY'
import urllib.request,sys
try: urllib.request.urlopen("https://openrouter.ai/api/v1/models",timeout=15); print("internet OK")
except Exception as e: print("NO INTERNET:",e); sys.exit(1)
PY
[ $? -ne 0 ] && { echo "ABORT: no internet"; exit 1; }
python experiments/syco_run.py --cases data/processed/echr_unified.json \
  --summaries data/processed/summaries_dsv41flash.json --out data/experiments/syco_full \
  --turns 3 --workers 100
echo "=== DONE $(date) ==="
