"""Build atomic-target candidates for post-v1.0 judgments. No model calls.

Uses the v1.0 target parser (rebuild_atomic_eval_set.py, recovered from repo history)
and records every exclusion with its reason.
"""
import json, re, sys, collections as C, hashlib
from pathlib import Path
W = Path.home() / 'lhrb-newcases'
sys.path.insert(0, str(W / 'archive_src')); sys.path.insert(0, str(W / 'repo' / 'experiments'))
import rebuild_atomic_eval_set as R
from targets import provision_name, target_question, target_key, target_stratum

GENERIC = 'the complaint identified under this provision'
MAX_CHARS = 50000
sha = lambda s: hashlib.sha256(s.encode('utf-8')).hexdigest()

# 1. parser regression on the v1.0 audit
audit = json.load(open(W / 'repo/data/audits/target_scope_audit.json'))['rows']
ok = n = 0; miss = []
for r in audit:
    h = r.get('official_holding')
    if not h or not r.get('target_issue'): continue
    n += 1
    p = R.conclusion_holdings(h, [r['target_respondent_code']])
    good = bool(p) and p[0]['article_full'] == r['target_article_full'] and p[0]['label'] == r['target_label'] and p[0]['target_issue'] == r['target_issue']
    ok += good
    if not good: miss.append((h[:110], r['target_issue'][:70], r['repairs']))
print('parser regression on v1.0 audit', ok, '/', n)
for m in miss[:6]: print('  miss', m)

v1 = json.load(open(W / 'pinned/echr_unified_v1.0.json'))
ids = {r['item_id'] for r in v1}; eclis = {r['ecli'] for r in v1 if r.get('ecli')}
apps = {a.strip() for r in v1 for a in str(r.get('application_number') or '').split(';') if a.strip()}

meta = json.load(open(W / 'raw/hudoc_meta.json'))
rows = json.load(open(W / 'raw/candidates_refreshed.json'))
text = {}
method = {}
for r in rows:
    if str(r.get('decision_date', '')) >= '2026-05-22' and r.get('full_case_text_no_verdict'):
        text.setdefault(r['item_id'], r['full_case_text_no_verdict']); method.setdefault(r['item_id'], r.get('verdict_removal_method'))

targets, excl = [], []
def drop(m, reason, **kw):
    excl.append({'item_id': m['itemid'], 'case_name': m['docname'], 'decision_date': m['kpdate'][:10], 'importance': m['importance'], 'branch': m['doctypebranch'], 'reason': reason, **kw})

for m in meta['rows']:
    iid = m['itemid']; appnos = [a.strip() for a in (m.get('appno') or '').split(';') if a.strip()]
    if m['kpdate'][:10] < '2026-05-22': drop(m, 'before_window'); continue
    if iid in ids: drop(m, 'overlap_item_id'); continue
    if m.get('ecli') in eclis: drop(m, 'overlap_ecli'); continue
    shared = sorted(set(appnos) & apps)
    if shared: drop(m, 'overlap_application_number', shared=shared); continue
    if iid not in text: drop(m, 'no_source_text_or_no_scraped_target'); continue
    src = text[iid][:MAX_CHARS]
    if len(src.strip()) < 500: drop(m, 'source_shorter_than_500_chars', n=len(src)); continue
    try:
        opts = R.candidates(m)
    except KeyError as e:
        drop(m, 'unmapped_respondent', code=str(e)); continue
    if not opts:
        drop(m, 'no_single_respondent_holding_resolved', conclusion=(m.get('conclusion') or '')[:300]); continue
    seen, usable = set(), []
    for o in opts:
        if o['target_issue'] == GENERIC: continue
        k = (iid, o['target_respondent_code'], o['article_full'], o['target_issue'].casefold())
        if k in seen:
            continue
        seen.add(k); usable.append(o)
    # A key holding two different outcomes cannot be an unambiguous target.
    by = C.defaultdict(set)
    for o in opts: by[(o['target_respondent_code'], o['article_full'], o['target_issue'].casefold())].add(o['label'])
    usable = [o for o in usable if len(by[(o['target_respondent_code'], o['article_full'], o['target_issue'].casefold())]) == 1]
    if not usable: drop(m, 'no_specific_unambiguous_issue'); continue
    for o in usable:
        art = o['article_full']; name = o['target_respondent']
        row = {
            'item_id': iid, 'case_name': m['docname'], 'respondent': name.removeprefix('the ').upper(),
            'decision_date': m['kpdate'][:10], 'article': art, 'article_full': art,
            'violation_label': o['label'], 'full_case_text_no_verdict': text[iid],
            'application_number': ';'.join(appnos), 'ecli': m.get('ecli', ''), 'importance': m.get('importance', ''),
            'branch': m.get('doctypebranch', ''), 'pair_id': iid,
            'target_respondent_code': o['target_respondent_code'], 'target_respondent': name,
            'target_provision': provision_name(art), 'target_issue': o['target_issue'], 'target_aspect': o['target_aspect'],
            'target_question': target_question(name, art, o['target_issue']), 'target_status': 'verified',
            '_stratum': target_stratum(art), '_method': method.get(iid), '_holding_index': o['holding_index'],
            '_official_holding': o['fragment'], '_assignment': o['assignment'], '_source_sha256': sha(src),
        }
        targets.append(row)

(W / 'work').mkdir(exist_ok=True)
json.dump(targets, open(W / 'work/targets_all.json', 'w'), ensure_ascii=False)
json.dump({'exclusions': excl}, open(W / 'work/exclusions_stage1.json', 'w'), ensure_ascii=False, indent=1)
# one row per judgment, the shape review_input_leakage.py expects
by = {}
for t in targets: by.setdefault(t['item_id'], t)
json.dump(list(by.values()), open(W / 'work/sources_for_review.json', 'w'), ensure_ascii=False)
print('meta', len(meta['rows']), 'targets', len(targets), 'judgments', len(by))
print('excl', C.Counter(e['reason'] for e in excl).most_common())
print('labels', C.Counter(t['violation_label'] for t in targets))
nv = {t['item_id'] for t in targets if t['violation_label'] == 'no_violation'}
print('judgments with a no_violation target', len(nv))
print('branch', C.Counter(t['branch'] for t in by.values()))
print('month', sorted(C.Counter(t['decision_date'][:7] for t in by.values()).items()))
print('articles', C.Counter(t['article_full'] for t in targets).most_common(25))
print('procedural', C.Counter(t['_stratum'] for t in targets))
L = sorted(len(t['full_case_text_no_verdict']) for t in by.values())
print('source chars median', L[len(L)//2], 'p10', L[len(L)//10], 'min', L[0], 'max', L[-1])
