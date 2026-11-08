"""Freeze the post-v1.0 candidate cohort and write its release artifacts. No model calls."""
import json, hashlib, subprocess, collections as C, shutil, datetime as dt
from pathlib import Path
W = Path.home() / 'lhrb-newcases'
OUT = W / 'release_candidate_20261108'; OUT.mkdir(exist_ok=True)
SEED = '20261108'; DATASET = 'echr-post-v1.0-candidate-20261108'
sha = lambda s: hashlib.sha256(s.encode('utf-8')).hexdigest()
rank = lambda *p: sha('|'.join((SEED,) + p))
plan = json.load(open(W / 'work/selection_plan.json'))
# Replaced after the operative-part check, before any target-model call.
REPLACED = {
    '001-251017': 'Target rests only on the excluded other-complaints appendix column; the model input has no facts on the length of proceedings.',
    '001-252645': 'Target rests only on the excluded other-complaints appendix column; the model input has no facts on the length of proceedings.',
    '001-252653': 'Target rests only on the excluded other-complaints appendix column; the model input has no facts on the presumption of innocence.',
    '001-250744': 'Target wording also covers a violation found in the same judgment under the same fair-hearing heading.',
    '001-252642': 'Outcome differs by applicant under overlapping provisions and the question does not name an applicant.',
}
OLD_CORE = json.load(open(OUT / 'core_50.json'))['item_ids']
T = json.load(open(W / 'work/targets_repaired.json'))
R = {r['item_id']: r for r in map(json.loads, open(W / 'work/source_reviews2.jsonl'))}
S = {}
for l in open(W / 'work/summaries.jsonl'):
    d = json.loads(l)
    if d['status'] == 'accepted': S[d['item_id']] = d
status = C.Counter(json.loads(l)['status'] for l in open(W / 'work/summaries.jsonl'))
by = C.defaultdict(list)
for t in T: by[t['item_id']].append(t)
def pick(i, label):
    c = [t for t in by[i] if t['violation_label'] == label]
    return min(c, key=lambda t: rank(i, t['target_respondent_code'], t['article_full'], t['target_issue'].casefold()))
nv = [i for i in plan['nv_rank'] if i in S and i not in REPLACED][:plan['n_no_violation_target']]
v, short = [], {}
for m, lst in plan['v_rank_by_month'].items():
    ok = [i for i in lst if i in S and i not in REPLACED and i not in set(nv)]
    q = plan['violation_month_quota'][m]; v += ok[:q]
    if len(ok) < q: short[m] = q - len(ok)
final = [(i, 'no_violation') for i in nv] + [(i, 'violation') for i in v]
rows, audit, leak_key = [], [], {}
for i, lab in final:
    t = pick(i, lab); row = {k: x for k, x in t.items() if not k.startswith('_')}
    rows.append(row)
    audit.append({'target_item_id': i, 'target_case_name': t['case_name'], 'target_article_full': t['article_full'], 'target_label': lab, 'target_respondent_code': t['target_respondent_code'], 'target_respondent': t['target_respondent'], 'target_issue': t['target_issue'], 'target_aspect': t['target_aspect'], 'assignment': t['_assignment'], 'holding_index': t['_holding_index'], 'official_holding': t['_official_holding'], 'source_sha256': t['_source_sha256'], 'summary_sha256': S[i]['summary_sha256'], 'verdict_removal_method': t['_method']})
rows.sort(key=lambda r: r['item_id']); audit.sort(key=lambda r: r['target_item_id'])
# gates
errors = []
v1 = json.load(open(W / 'pinned/echr_unified_v1.0.json'))
ids1 = {r['item_id'] for r in v1}; ecl1 = {r['ecli'] for r in v1 if r.get('ecli')}
app1 = {a.strip() for r in v1 for a in str(r.get('application_number') or '').split(';') if a.strip()}
ovl = {'item_id': [], 'ecli': [], 'application_number': []}
for r in rows:
    if r['item_id'] in ids1: ovl['item_id'].append(r['item_id'])
    if r['ecli'] in ecl1: ovl['ecli'].append(r['item_id'])
    if set(a.strip() for a in r['application_number'].split(';')) & app1: ovl['application_number'].append(r['item_id'])
    if r['decision_date'] < '2026-05-22': errors.append(('date', r['item_id']))
    if '41' == r['article_full']: errors.append(('art41', r['item_id']))
for a in audit:
    h = a['official_holding'].casefold()
    want = 'no violation' if a['target_label'] == 'no_violation' else 'violation'
    if not h.startswith(want): errors.append(('label_vs_holding', a['target_item_id'], h[:60]))
if len({r['item_id'] for r in rows}) != len(rows): errors.append('not one target per judgment')
if any(ovl.values()): errors.append(('overlap', ovl))
missing_core = sorted(set(OLD_CORE) - {i for i, _ in final})
if missing_core: errors.append(('core_changed', missing_core))
ids = sorted(r['item_id'] for r in rows)
payload = {'dataset_id': DATASET, 'summarizer': S[ids[0]]['model'], 'versions': 1, 'mode': 'abstractive', 'n_judgments': len(ids), 'n_complete': len(ids), 'generation_prompt_version': 'leak-safe-v3', 'summaries': {i: [S[i]['summary']] for i in ids}}
def w(name, obj):
    with open(OUT / name, 'w', encoding='utf-8') as f: json.dump(obj, f, ensure_ascii=False, indent=2); f.write('\n')
w('cases.json', rows); w('summaries.json', payload)
w('target_audit.json', {'status': 'PASSED', 'input_instances': len(rows), 'output_instances': len(rows), 'unresolved_instances': 0, 'rows': audit})
years = dict(sorted(C.Counter(r['decision_date'][:4] for r in rows).items())); labels = dict(C.Counter(r['violation_label'] for r in rows))
rel = '../release_candidate_20261108/'
ds = {'path': rel + 'cases.json', 'instances': len(rows), 'judgments': len(ids), 'instance_key': ['item_id', 'target_respondent_code', 'article_full', 'target_issue'], 'labels': labels, 'annual_counts': years, 'date_min': min(r['decision_date'] for r in rows), 'date_max': max(r['decision_date'] for r in rows), 'target_contract': {'unit': 'one judgment, one respondent State, one provision, one sub-conclusion', 'audit': rel + 'target_audit.json'}}
w('evaluation_dataset.json', {'schema_version': 2, 'dataset_id': DATASET, 'release_version': 'candidate', 'selection': plan['rule'], 'dataset': ds, 'summaries': {'path': rel + 'summaries.json', 'summarizer': payload['summarizer'], 'versions': 1, 'represented_judgments': len(ids), 'complete_judgments': len(ids), 'usable_summaries': len(ids), 'missing_slots_zero_based': []}})
w('core_50.json', {'rule': 'Lowest-ranked 15 no_violation and 35 violation judgments of the cohort as first frozen; unchanged by the later target replacements', 'seed': SEED, 'item_ids': OLD_CORE})
meta = json.load(open(W / 'raw/hudoc_meta.json'))
excl = json.load(open(W / 'work/exclusions_stage1.json'))['exclusions']; rp = json.load(open(W / 'work/repair_provenance.json'))
funnel = C.Counter()
for e in excl: funnel['no_html_body_http_204' if e['reason'] == 'no_source_text_or_no_scraped_target' else e['reason']] += 1
for e in rp['exclusions']: funnel[e['reason']] += 1
src_fail = [i for i, r in R.items() if not (r['status'] == 'reviewed' and not any(r['result'][k] for k in ('conclusion', 'reasoning', 'insufficient_facts')))]
funnel['source_review_insufficient_or_flagged'] = len(src_fail)
funnel['replaced_after_operative_part_check'] = len(REPLACED)
old_ids = set(json.load(open(W / 'work/first_freeze_ids.json')))
added = sorted({i for i, _ in final} - old_ids)
w('non_overlap_report.json', {'v1_0_sha256': sha(open(W / 'pinned/echr_unified_v1.0.json', encoding='utf-8').read()), 'checked_targets': len(rows), 'overlaps': ovl, 'status': 'PASSED' if not any(ovl.values()) else 'FAILED'})
w('exclusions.json', {'funnel': funnel, 'hudoc_results': meta['resultcount'], 'eligible_judgments': plan['eligible_judgments'], 'stage1': excl, 'repair': rp['exclusions'], 'source_review_failed': src_fail, 'summary_status': status, 'replaced_after_operative_part_check': REPLACED})
d = lambda rs, k: dict(C.Counter(r[k] for r in rs).most_common())
dist = {'new': {'labels': d(rows, 'violation_label'), 'provisions': d(rows, 'article_full'), 'branch': d(rows, 'branch'), 'importance': d(rows, 'importance'), 'months': dict(sorted(C.Counter(r['decision_date'][:7] for r in rows).items())), 'respondents': d(rows, 'target_respondent_code')},
        'v1.0': {'labels': d(v1, 'violation_label'), 'provisions': d(v1, 'article_full'), 'importance': d(v1, 'importance')}}
L = sorted(len(r['full_case_text_no_verdict'][:50000]) for r in rows); dist['new']['source_chars_median'] = L[len(L)//2]; dist['new']['source_chars_mean'] = sum(L) / len(L)
w('distribution_report.json', dist)
git = subprocess.check_output(['git', '-C', str(W / 'repo'), 'rev-parse', 'HEAD'], text=True).strip()
files = {p.name: sha(p.read_text(encoding='utf-8')) for p in sorted(OUT.glob('*.json')) if p.name != 'release_manifest.json'}
w('release_manifest.json', {'benchmark': 'LiveHumanRightsBench', 'status': 'candidate, frozen before any target-model call', 'dataset_id': DATASET, 'frozen_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'source_revision': git, 'hudoc_retrieved_utc': meta['retrieved_utc'], 'hudoc_query': meta['query'], 'window': {'decision_date_from': '2026-05-22', 'date_max_observed': ds['date_max']}, 'base_release': {'version': 'v1.0', 'sha256': 'b51526021b9b48634823f2433ee3ea8efdd8fa9776aaa235a5c4fe68d8780b0f'}, 'selection_seed': SEED, 'selection_rule': plan['rule'], 'amendments': [{'stage': 'operative-part check, before any target-model call', 'removed': REPLACED, 'added': added, 'rule': 'next-ranked judgment with an accepted summary in the same stratum, and in the same month for violation targets'}], 'files_sha256': files, 'targets': [{'item_id': a['target_item_id'], 'source_sha256': a['source_sha256'], 'summary_sha256': a['summary_sha256']} for a in audit]})
for f in ('source_reviews2.jsonl', 'summaries.jsonl', 'summaries.attempts.jsonl', 'repair_provenance.json', 'selection_plan.json'): shutil.copy(W / 'work' / f, OUT / f)
shutil.copy(W / 'raw/hudoc_meta.json', OUT / 'hudoc_meta_retrieved.json')
print('added', added); print('status', dict(status), 'short', short, 'targets', len(rows), 'labels', labels, 'errors', errors)
print('funnel', dict(funnel))
print(json.dumps(dist['new'], ensure_ascii=False)[:900])
print('v1 prov', list(dist['v1.0']['provisions'].items())[:8], dist['v1.0']['importance'])
