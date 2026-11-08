"""Apply the v1.0 structural source repair and factual-appendix recovery. No model calls.

HTML is fetched only for sources that need an appendix, through the project's own
scraper settings and the same document endpoint it already uses.
"""
import json, re, sys, time, hashlib, collections as C
from pathlib import Path
W = Path.home() / 'lhrb-newcases'
sys.path.insert(0, str(W / 'archive_src')); sys.path.insert(0, str(W / 'repo/scripts'))
from leak_audit.boundaries import repair
from leak_audit.factual_tables import extract
import hudoc_scraper as H
import requests
FIELD = 'full_case_text_no_verdict'
sha = lambda s: hashlib.sha256(s.encode('utf-8')).hexdigest()
APPX = re.compile(r'append(?:ed|ix).*?(?:table|list)|table.*?append', re.I)
targets = json.load(open(W / 'work/targets_all.json'))
by = {}
for t in targets: by.setdefault(t['item_id'], t)
cache = W / 'raw/html'; cache.mkdir(exist_ok=True)
sess = requests.Session()
clean, prov, excl = {}, [], []
def html_for(iid):
    p = cache / f'{iid}.html'
    if p.exists(): return p.read_text(encoding='utf-8')
    r = sess.get(f'{H.HUDOC_DOC_BODY_URL}?library=ECHR&id={iid}', headers=H.HEADERS, timeout=120)
    r.raise_for_status(); time.sleep(1.5)
    p.write_text(r.text, encoding='utf-8'); return r.text
for iid, t in by.items():
    old = t[FIELD]; rec = {'item_id': iid, 'old_chars': len(old), 'old_sha256': sha(old)}
    try:
        new, spans = repair(old)
    except ValueError as e:
        excl.append({'item_id': iid, 'reason': 'structural_repair_unresolved', 'detail': str(e)}); continue
    rec['removed_spans'] = [{k: v for k, v in s.items() if k != 'boundary_context'} for s in spans]
    rec['appendix'] = None
    if len(new) < 6000 and APPX.search(new):
        try:
            html = html_for(iid)
            if not html.strip(): raise ValueError('empty HUDOC body')
            details, inc, exc = extract(html, t['application_number'])
            new += '\n\nFACTUAL DETAILS FROM THE APPENDED TABLE\n' + details
            rec['appendix'] = {'included_columns': inc, 'omitted_columns': exc, 'facts_sha256': sha(details)}
        except (ValueError, requests.RequestException) as e:
            excl.append({'item_id': iid, 'reason': 'factual_appendix_unresolved', 'detail': str(e)[:300]}); continue
    if len(new.strip()) < 500:
        excl.append({'item_id': iid, 'reason': 'repaired_source_shorter_than_500_chars'}); continue
    rec.update(new_chars=len(new), new_sha256=sha(new), input_changed=old[:50000] != new[:50000])
    clean[iid] = new; prov.append(rec)
out = []
for t in targets:
    if t['item_id'] in clean:
        s = clean[t['item_id']]
        out.append({**t, FIELD: s, '_source_sha256': sha(s[:50000])})
json.dump(out, open(W / 'work/targets_repaired.json', 'w'), ensure_ascii=False)
first = {}
for t in out: first.setdefault(t['item_id'], t)
json.dump(list(first.values()), open(W / 'work/sources_for_review2.json', 'w'), ensure_ascii=False)
json.dump({'changes': prov, 'exclusions': excl}, open(W / 'work/repair_provenance.json', 'w'), ensure_ascii=False, indent=1)
print('kept judgments', len(clean), 'targets', len(out), 'excl', C.Counter(e['reason'] for e in excl).most_common())
print('span reasons', C.Counter(s['reason'] for p in prov for s in p['removed_spans']).most_common())
print('appendix recovered', sum(bool(p['appendix']) for p in prov))
for e in excl[:6]: print(e)
L = sorted(len(v) for v in clean.values()); print('chars median', L[len(L)//2], 'min', L[0], 'p90', L[int(.9*len(L))])
