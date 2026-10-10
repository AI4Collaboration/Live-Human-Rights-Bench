#!/bin/bash
#SBATCH --job-name=para_regen2
#SBATCH --account=def-zhijing
#SBATCH --time=8:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --output=para_regen2_%j.log
set -euo pipefail
ROOT=${SLURM_SUBMIT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
cd "$ROOT"
export PYTHONUNBUFFERED=1
: "${OPENROUTER_API_KEY:?Set OPENROUTER_API_KEY}"

PAIRS=data/processed/paraphrase_pairs_regen_cut.json
OUT=data/experiments/paraphrase_regen2
# only the models that dropped samples on the long inputs (qwen3-235b is unavailable, skip)
MODELS="deepseek/deepseek-v4-pro deepseek/deepseek-v4-flash qwen/qwen3-32b"

echo "=== re-score 26 targets with bigger budget + retry-on-unparse ==="
for m in $MODELS; do
  echo "-- $m"
  python experiments/paraphrase_run.py eval --model "$m" --pairs "$PAIRS" --out "$OUT" \
    --samples 10 --workers 40 --max-tokens 8000 --unparsed-retries 3
done

echo "=== swap in ONLY improved rows (no regressions) ==="
python - <<'PY'
import json, os
keys={(p['item_id'],p['article']) for p in json.load(open('data/processed/paraphrase_pairs_regen_cut.json'))}
base="data/experiments/paraphrase"; new="data/experiments/paraphrase_regen2"
def better(old,n):
    # prefer a parsed average; among parsed, prefer fewer unparsed samples
    if n['avg_rating'] is None: return False
    if old['avg_rating'] is None: return True
    return n.get('n_unparsed',0) <= old.get('n_unparsed',0)
for d in sorted(os.listdir(new)):
    mp=os.path.join(base,d,"paraphrase_results.jsonl"); rp=os.path.join(new,d,"paraphrase_results.jsonl")
    if not os.path.exists(mp): print("  SKIP",d); continue
    main=[json.loads(l) for l in open(mp) if l.strip()]
    nw={(r['item_id'],r['article'],r['arm']):r for r in (json.loads(l) for l in open(rp) if l.strip())}
    idx={(r['item_id'],r['article'],r['arm']):i for i,r in enumerate(main)}
    repl=0
    for key3,n in nw.items():
        i=idx.get(key3)
        if i is not None and (main[i]['item_id'],main[i]['article']) in keys and better(main[i],n):
            main[i]=n; repl+=1
    with open(mp,"w",encoding="utf-8",newline="\n") as h:
        for r in main: h.write(json.dumps(r,ensure_ascii=False)+"\n")
    un=sum(r.get('n_unparsed',0) for r in main if (r['item_id'],r['article']) in keys)
    nul=sum(1 for r in main if (r['item_id'],r['article']) in keys and r['avg_rating'] is None)
    print(f"  {d}: improved {repl} rows | regen-target unparsed now {un} | nulls {nul}")
PY
echo "=== ALL DONE ==="
