#!/usr/bin/env bash
# Run the full frontier roster over every arm, N models at a time.
#
# Each model is a separate process with its own checkpoint directory, so a model
# that dies takes only itself down and resumes from where it stopped. Slugs are
# fully qualified on purpose: "openai/gpt-5.6" is ambiguous between terra, sol and
# luna, which differ tenfold in price, and a bare alias resolves silently.
#
#   OPENROUTER_API_KEY=... MLFLOW_TRACKING_PASSWORD=... ./scripts/run_roster.sh
#
# Env knobs: CONC (models at once, default 6), WORKERS_OVERRIDE (flat worker count,
# overriding the calibrated per-model values), RQ (arms, default all), SAMPLES,
# OUT, CASES, SUMMARIES.
set -uo pipefail

# Canonical evaluation pool: approximately equal case counts across years.
CASES=${CASES:-data/processed/echr_unified.json}
SUMMARIES=${SUMMARIES:-data/processed/summaries_dsv41flash.json}
# Keep the unified/DeepSeek run separate from historical Grok checkpoints.
OUT=${OUT:-data/experiments/unified_dsv41flash_leakchecked_20260916}
SAMPLES=${SAMPLES:-3}
CONC=${CONC:-6}   # all six at once; the gate exists for smaller reruns
# Which arms to run. All summary-based arms, including RQ3, use the supplied
# canonical summary artifact.
RQ=${RQ:-all}
LOGS=${LOGS:-logs/unified_dsv41flash_leakchecked_20260916}

# Run every model at 69 workers, the highest concurrency in the previous roster.
# This is an explicit throughput choice and is kept identical across providers.
MODELS=(
  "qwen/qwen3-32b:69"
  "qwen/qwen3-235b-a22b:69"
  "deepseek/deepseek-v4-pro:69"
  "deepseek/deepseek-v4-flash:69"
  "openai/gpt-5.6-sol:69"
  "anthropic/claude-opus-4.8:69"
)

: "${OPENROUTER_API_KEY:?set OPENROUTER_API_KEY}"
export MLFLOW_TRACKING_URI=${MLFLOW_TRACKING_URI:-https://mlflow.lex}
export MLFLOW_TRACKING_USERNAME=${MLFLOW_TRACKING_USERNAME:-admin}
export MLFLOW_TRACKING_INSECURE_TLS=${MLFLOW_TRACKING_INSECURE_TLS:-true}
: "${MLFLOW_TRACKING_PASSWORD:?set MLFLOW_TRACKING_PASSWORD}"

for f in "$CASES" "$SUMMARIES"; do
  [ -f "$f" ] || { echo "missing $f"; exit 1; }
done
mkdir -p "$LOGS" "$OUT"

echo "cases=$CASES summaries=$SUMMARIES samples=$SAMPLES conc=$CONC rq=$RQ"
echo "models: ${#MODELS[@]}   logs: $LOGS"
echo

start=$(date +%s)
for entry in "${MODELS[@]}"; do
  model=${entry%:*}; w=${entry##*:}
  [ -n "${WORKERS_OVERRIDE:-}" ] && w=$WORKERS_OVERRIDE
  while [ "$(jobs -rp | wc -l)" -ge "$CONC" ]; do wait -n; done
  slug=${model//\//_}; slug=${slug//./_}
  echo "[$(date +%H:%M:%S)] start $model with $w workers"
  python3 experiments/run_perturbation_openai.py \
      --cases "$CASES" --summaries "$SUMMARIES" --model "$model" \
      --base-url https://openrouter.ai/api/v1 --api-key-env OPENROUTER_API_KEY \
      --samples "$SAMPLES" --workers "$w" --rq "$RQ" \
      --output-dir "$OUT" > "$LOGS/$slug.log" 2>&1 &
done
wait
echo
echo "[$(date +%H:%M:%S)] roster finished in $(( ($(date +%s) - start) / 60 )) min"

# A model that failed leaves a short log and no results; say so rather than
# letting the analysis quietly run on seven models and read as eight.
for entry in "${MODELS[@]}"; do
  model=${entry%:*}
  slug=${model//\//_}; slug=${slug//./_}
  for arm in $([ "$RQ" = all ] && echo baseline rq1 rq2 rq3 || echo "$RQ"); do
    [ -s "$OUT/$slug/${arm}_results.json" ] || echo "MISSING $slug/$arm"
  done
done

echo
echo "next: python3 scripts/analyse_perturbation_run.py --run-dir $OUT"
