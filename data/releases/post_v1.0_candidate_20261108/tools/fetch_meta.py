"""Pull HUDOC metadata the scraper output drops (ECLI, application numbers, conclusion text)."""
import json, sys, time, datetime as dt, hashlib
import requests
OUT = sys.argv[1]
Q = ('contentsitename:ECHR AND (NOT (doctype=PR OR doctype=HFCOMOLD OR doctype=HECOMOLD)) '
     'AND (documentcollectionid="JUDGMENTS") AND (languageisocode="ENG") AND kpdate>="2026-05-22T00:00:00.0Z"')
F = 'itemid,docname,appno,ecli,kpdate,importance,doctypebranch,conclusion,article,respondent,respondentOrderEng,separateopinion,originatingbody,violation,nonviolation,scl,languageisocode'
rows, start, total = [], 0, None
s = requests.Session(); s.headers['User-Agent'] = 'LiveHumanRightsBench-refresh'
while total is None or start < total:
    r = s.get('https://hudoc.echr.coe.int/app/query/results', params={'query': Q, 'select': F, 'sort': 'kpdate Descending', 'start': start, 'length': 100}, timeout=60)
    r.raise_for_status(); d = r.json(); total = d['resultcount']
    batch = [x['columns'] for x in d['results']]
    if not batch: break
    rows += batch; start += len(batch); time.sleep(1.0)
ids = [x['itemid'] for x in rows]
assert len(ids) == len(set(ids)), 'duplicate item ids'
retrieved = dt.datetime.now(dt.timezone.utc).isoformat()
payload = {'retrieved_utc': retrieved, 'query': Q, 'resultcount': total, 'rows': rows}
json.dump(payload, open(OUT, 'w'), ensure_ascii=False, indent=1)
print('rows', len(rows), 'of', total, retrieved)
