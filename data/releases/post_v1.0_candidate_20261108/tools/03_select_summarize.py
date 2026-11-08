"""Pre-specified target selection, then v1.0-protocol summaries for the ranked pool.

Selection reads only target metadata and hash ranks; no model prediction exists yet.
Summaries use the v1.0 generator; the reviewer is DeepSeek v4.1 Flash, not an evaluated model.
"""
import json, os, sys, hashlib, math, collections as C, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
W = Path.home() / 'lhrb-newcases'
sys.path.insert(0, str(W / 'archive_src')); sys.path.insert(0, str(W / 'repo/experiments'))
SEED = '20261108'; N_NV, N_V = 30, 70
SPARE = 1.25
sha = lambda s: hashlib.sha256(s.encode('utf-8')).hexdigest()
rank = lambda *p: sha('|'.join((SEED,) + p))
T = json.load(open(W / 'work/targets_repaired.json'))
R = {r['item_id']: r for r in map(json.loads, open(W / 'work/source_reviews2.jsonl'))}
def passed(r): return r and r['status'] == 'reviewed' and not any(r['result'][k] for k in ('conclusion', 'reasoning', 'insufficient_facts'))
eligible = [t for t in T if passed(R.get(t['item_id']))]
by = C.defaultdict(list)
for t in eligible: by[t['item_id']].append(t)
def pick(item, label):
    c = [t for t in by[item] if t['violation_label'] == label]
    return min(c, key=lambda t: rank(item, t['target_respondent_code'], t['article_full'], t['target_issue'].casefold())) if c else None
ids = sorted(by, key=lambda i: rank(i))
nv_rank = [i for i in ids if pick(i, 'no_violation')]
nv_sel = nv_rank[:N_NV]
v_pool = [i for i in ids if i not in set(nv_sel) and pick(i, 'violation')]
months = C.Counter(by[i][0]['decision_date'][:7] for i in v_pool)
tot = sum(months.values())
raw = {m: N_V * n / tot for m, n in months.items()}
quota = {m: math.floor(x) for m, x in raw.items()}
for m in sorted(raw, key=lambda m: (-(raw[m] - quota[m]), m))[:N_V - sum(quota.values())]: quota[m] += 1
plan = {'seed': SEED, 'rule': 'One target per judgment. no_violation stratum: up to 30 judgments by SHA-256 rank of seed|item_id, taking the lowest-ranked no_violation target. violation stratum: 70 targets allocated across decision months by largest remainder in proportion to eligible judgments, ranked within month by the same hash; lowest-ranked violation target per judgment. Substitutes are the next ranked judgment in the same stratum and month. Core 50 = lowest-ranked 15 no_violation + 35 violation.',
        'n_no_violation_target': N_NV, 'n_violation_target': N_V, 'violation_month_quota': quota,
        'eligible_judgments': len(by), 'eligible_no_violation_judgments': len(nv_rank)}
tasks = []
for i in nv_rank: tasks.append((i, 'no_violation', pick(i, 'no_violation')))
pm = C.defaultdict(list)
for i in v_pool: pm[by[i][0]['decision_date'][:7]].append(i)
for m, lst in pm.items():
    for i in lst[:max(quota[m] + 2, math.ceil(quota[m] * SPARE))]:
        tasks.append((i, 'violation', pick(i, 'violation')))
json.dump({**plan, 'nv_rank': nv_rank, 'v_rank_by_month': pm, 'generated_for': [t[0] for t in tasks]}, open(W / 'work/selection_plan.json', 'w'), indent=1)
print({k: v for k, v in plan.items() if k != 'rule'}, 'summaries to generate', len(tasks), flush=True)
from resummarize import generate, MODEL, digest
from openai import OpenAI
client = OpenAI(base_url='https://openrouter.ai/api/v1', api_key=os.environ['OPENROUTER_API_KEY'], timeout=180, max_retries=1)
out = W / 'work/summaries.jsonl'; att = W / 'work/summaries.attempts.jsonl'
done = {}
if out.exists():
    for l in open(out):
        d = json.loads(l)
        if d['status'] == 'accepted': done[d['item_id']] = d
lock = threading.Lock()
def journal(row):
    with lock, open(att, 'a', encoding='utf-8') as f: f.write(json.dumps(row, ensure_ascii=False) + '\n')
def run(iid, t):
    src = t['full_case_text_no_verdict'][:50000]
    task = {'key': f'{iid}:0', 'item_id': iid, 'version': 0, 'case_name': t['case_name'], 'source': src, 'source_sha256': digest(src), 'generation_prompt_version': 'leak-safe-v3', 'reason': 'new_release_candidate'}
    return generate(client, task, MODEL, journal)
pending = [(i, t) for i, _, t in tasks if i not in done]
n = C.Counter()
with open(out, 'a', encoding='utf-8') as f, ThreadPoolExecutor(max_workers=6) as pool:
    fut = [pool.submit(run, i, t) for i, t in pending]
    for k, x in enumerate(as_completed(fut), 1):
        r = x.result(); r.update(model=MODEL, temperature=1.0, review_model=MODEL)
        f.write(json.dumps(r, ensure_ascii=False) + '\n'); f.flush(); n[r['status']] += 1
        print(k, '/', len(pending), dict(n), flush=True)
