#!/bin/bash
#SBATCH --job-name=lhrb_v1anchor_100
#SBATCH --account=def-zhijing
#SBATCH --time=12:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --output=eval_v1anchor_%j.log
set -uo pipefail
cd /scratch/ariankh/Legal-Sycophancy/lhrb-v1anchor-eval
export PYTHONUNBUFFERED=1
export OPENROUTER_API_KEY=$(cat ~/.openrouter_key)
PY=/home/ariankh/legalllms/bin/python
cred(){ curl -s https://openrouter.ai/api/v1/credits -H "Authorization: Bearer $OPENROUTER_API_KEY" | $PY -c "import json,sys;print(json.load(sys.stdin)['data']['total_usage'])"; }
echo "COHORT: v1.0 anchor 100 (same serving window)"
echo "USAGE_BEFORE=$(cred)"
for m in openai/gpt-5.6-sol anthropic/claude-opus-4.6; do
  for RQ in baseline rq1; do
    echo "== fullcase $m $RQ =="
    $PY experiments/run_perturbation_fullcase.py \
      --cases data/processed/echr_unified.json \
      --summaries data/processed/summaries_dsv41flash.json \
      --model "$m" --base-url https://openrouter.ai/api/v1 \
      --api-key-env OPENROUTER_API_KEY --samples 10 --workers 20 --rq $RQ \
      --output-dir data/experiments/v1_anchor_100/fullcase
  done
done
echo "== syco (baseline_high + authority_researcher) =="
$PY experiments/syco_run.py \
  --cases data/processed/echr_unified.json \
  --summaries data/processed/summaries_dsv41flash.json \
  --out data/experiments/v1_anchor_100/syco \
  --targets openai/gpt-5.6-sol anthropic/claude-opus-4.6 --turns 3 --workers 20
echo "USAGE_AFTER=$(cred)"
echo "ALL_DONE"
