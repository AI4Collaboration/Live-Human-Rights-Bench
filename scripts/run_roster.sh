#!/usr/bin/env bash
# Full-case and shared-summary evaluation for the current six-model roster.
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
: "${OPENROUTER_API_KEY:?Set OPENROUTER_API_KEY in the environment}"
export MLFLOW_TRACKING_URI=${MLFLOW_TRACKING_URI:-file:./mlruns}
export PYTHONUNBUFFERED=1
CASES=${CASES:-data/processed/echr_unified.json}
SUMMARIES=${SUMMARIES:-data/processed/summaries_dsv41flash.json}
OUT=${OUT:-data/experiments/fullcase_new}
LOGS=${LOGS:-logs/fullcase_new}
SAMPLES=${SAMPLES:-10}
WORKERS=${WORKERS:-20}
CONC=${CONC:-6}
[[ "$CONC" =~ ^[1-9][0-9]*$ ]] || { echo "CONC must be a positive integer"; exit 1; }
MODELS=(openai/gpt-5.6-sol anthropic/claude-opus-4.6
        deepseek/deepseek-v4-pro deepseek/deepseek-v4-flash
        qwen/qwen3-235b-a22b qwen/qwen3-32b)
mkdir -p "$LOGS"
pids=()
failed=0
wait_batch() {
  local pid
  for pid in "${pids[@]}"; do
    if ! wait "$pid"; then failed=1; fi
  done
  pids=()
}
for model in "${MODELS[@]}"; do
  slug=${model//\//_}
  python experiments/run_perturbation_fullcase.py \
    --cases "$CASES" --summaries "$SUMMARIES" --model "$model" \
    --base-url https://openrouter.ai/api/v1 --api-key-env OPENROUTER_API_KEY \
    --samples "$SAMPLES" --workers "$WORKERS" --rq all --output-dir "$OUT" \
    > "$LOGS/$slug.log" 2>&1 &
  pids+=("$!")
  if (( ${#pids[@]} >= CONC )); then wait_batch; fi
done
wait_batch
exit "$failed"
