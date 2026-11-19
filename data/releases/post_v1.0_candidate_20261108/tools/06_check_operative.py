"""Check each frozen target against the operative part of the published judgment. No model calls."""
import json, re, glob, collections as C, unicodedata
from pathlib import Path
W = Path.home() / 'lhrb-newcases'
cases = json.load(open(W / 'release_candidate_20261108/cases.json'))
full = {}
for r in json.load(open(glob.glob(str(W / 'raw/hudoc_raw_*.json'))[0])): full.setdefault(r['item_id'], r['full_case_text'])
norm = lambda s: re.sub(r'[ \t]+', ' ', s.replace('\xa0', ' ').replace(' ', ' '))
NEG = re.compile(r'\bno violation|not been (?:a )?(?:violation|breach)|no breach|not disclose (?:a|any) breach|no(?:t)? (?:been )?violated', re.I)
POS = re.compile(r'\bviolation|\bbreach|\bviolated', re.I)
def art_rx(code):
    m = re.fullmatch(r'P(\d+)-(\d+)', code)
    return re.compile(rf'Article {m.group(2)}\b(?: § ?\d+)? of Protocol No\. ?{m.group(1)}\b', re.I) if m else None
def operative(text):
    t = norm(text); m = list(re.finditer(r'FOR THESE REASONS', t))
    if not m: return None
    op = t[m[-1].end():]
    e = re.search(r'\n\s*Done in (?:English|French)', op)
    return op[:e.start()] if e else op
def points(op):
    flat = re.sub(r'\s+', ' ', op).strip()
    flat = re.sub(r'^,?\s*THE COURT,?(?: UNANIMOUSLY,?| BY A MAJORITY,?)?\s*', '', flat, flags=re.I)
    parts = re.split(r'[;.:]\s*(?:and\s+)?(?:\d+\.\s*)?(?=(?:Holds|Declares|Decides|Dismisses|Joins|Strikes|Rejects)\b)', flat)
    return [x.strip() for x in parts if x.strip()]
def mentions(pt, code):
    rx = art_rx(code)
    if rx:
        return bool(rx.search(pt))
    body = re.sub(r'Article \d+(?: § ?\d+)? of Protocol No\. ?\d+', ' ', pt)
    # the principal provisions are those before any "in conjunction with" clause
    head = re.split(r'in conjunction with|read together with|taken together with', body, 1)[0]
    nums = set()
    for m in re.finditer(r'Articles? ((?:\d+(?: § ?\d+)?(?:, | and | or )?)+)', head):
        nums |= set(re.findall(r'(?<![§\d] )(?<!§)\b(\d+)\b(?! §\d)', re.sub(r'§ ?\d+', '', m.group(1))))
    return code in nums
RES = C.Counter(); rows = []
for c in cases:
    i, code, lab = c['item_id'], c['article_full'], c['violation_label']
    t = full.get(i); r = {'item_id': i, 'case': c['case_name'], 'article': code, 'label': lab, 'issue': c['target_issue'], 'aspect': c['target_aspect']}
    title = norm(c['case_name']); resp = c['target_respondent'].removeprefix('the ')
    fold = lambda x: ''.join(ch for ch in unicodedata.normalize('NFKD', x.replace('İ', 'I').replace('ı', 'i')) if not unicodedata.combining(ch)).casefold()
    r['respondent_in_title'] = fold(resp) in fold(title) or {'Czechia': 'czech', 'North Macedonia': 'macedonia', 'Russia': 'russia', 'Republic of Moldova': 'moldova'}.get(resp, '\0') in fold(title)
    op = operative(t) if t else None
    if not op: r['status'] = 'NO_OPERATIVE_PART'; RES[r['status']] += 1; rows.append(r); continue
    pts = points(op); rel = []
    for p in pts:
        if re.match(r'^(Declares|Decides to join|Holds that there is no need|Dismisses|Joins|Holds that it is not necessary)', p) and not POS.search(p): continue
        if re.search(r'\bno need to|not necessary to examine', p, re.I): continue
        if not (NEG.search(p) or POS.search(p)): continue
        if re.search(r'^Holds?,? .*respondent State is to pay|to pay the applicant', p): continue
        if mentions(p, code): rel.append(('no_violation' if NEG.search(p) else 'violation', p))
    r['points'] = rel; pol = {a for a, _ in rel}
    if not rel: st = 'NOT_FOUND'
    elif pol == {lab}: st = 'MATCH_UNIFORM'
    elif lab in pol: st = 'MIXED_NEEDS_ISSUE_CHECK'
    else: st = 'CONTRADICTS'
    if not r['respondent_in_title']: st += '+RESPONDENT?'
    r['status'] = st; RES[st] += 1; rows.append(r)
json.dump(rows, open(W / 'work/operative_check.json', 'w'), ensure_ascii=False, indent=1)
print(RES.most_common())
mu = [r for r in rows if r['status'] == 'MATCH_UNIFORM' and len(r['points']) > 1]
print('uniform with several points on the provision:', len(mu))
for r in rows:
    if r['status'] != 'MATCH_UNIFORM':
        print('\n##', r['status'], r['item_id'], r['case'][:60], '| art', r['article'], r['label'], '|', r['issue'][:120], '| aspect', r['aspect'])
        for a, p in r.get('points', []): print('   ', a, '::', p[:330])
        if r['status'].startswith('NOT_FOUND') or r['status'].startswith('NO_OP'):
            op = operative(full[r['item_id']]) or ''
            print('   OP:', re.sub(r'\s+', ' ', op)[:900])
