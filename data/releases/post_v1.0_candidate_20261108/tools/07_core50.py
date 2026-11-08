#!/usr/bin/env python3
"""Write the core-50 subset of the frozen cohort as a self-contained cohort.

The experiment gate requires the run cases to match the active cohort exactly,
so the starting cohort needs its own cases, summaries, audit and manifest.
Usage: 07_core50.py <release-dir>
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

D = Path(sys.argv[1])
PREFIX = str(D).rstrip('/')
DATASET_ID = 'echr-post-v1.0-candidate-20261108-core50'


def read(name):
    return json.loads((D / name).read_text(encoding='utf-8'))


def write(name, obj):
    text = json.dumps(obj, ensure_ascii=False, indent=2) + '\n'
    (D / name).write_text(text, encoding='utf-8')
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


core = set(read('core_50.json')['item_ids'])
cases = [c for c in read('cases.json') if c['item_id'] in core]
if len(cases) != 50 or {c['item_id'] for c in cases} != core:
    raise SystemExit('core_50.json does not select 50 judgments from cases.json')

summaries = read('summaries.json')
summaries['dataset_id'] = DATASET_ID
summaries['summaries'] = {k: v for k, v in summaries['summaries'].items() if k in core}
summaries['n_judgments'] = summaries['n_complete'] = len(summaries['summaries'])

audit = read('target_audit.json')
audit['rows'] = [r for r in audit['rows'] if r['target_item_id'] in core]
audit['input_instances'] = audit['output_instances'] = len(audit['rows'])
if len(audit['rows']) != 50:
    raise SystemExit('target audit does not cover the core 50')

spec = read('evaluation_dataset.json')
spec['dataset_id'] = DATASET_ID
spec['selection'] = 'The 50 judgments listed in core_50.json, a subset of ' \
    'echr-post-v1.0-candidate-20261108. ' + spec['selection']
dates = [c['decision_date'] for c in cases]
spec['dataset'].update({
    'path': f'{PREFIX}/core_50_cases.json',
    'instances': 50,
    'judgments': 50,
    'labels': dict(Counter(c['violation_label'] for c in cases)),
    'annual_counts': dict(sorted(Counter(d[:4] for d in dates).items())),
    'date_min': min(dates),
    'date_max': max(dates),
})
spec['dataset']['target_contract']['audit'] = f'{PREFIX}/core_50_target_audit.json'
spec['summaries'].update({
    'path': f'{PREFIX}/core_50_summaries.json',
    'represented_judgments': 50,
    'complete_judgments': 50,
    'usable_summaries': 50,
})

hashes = {
    'core_50_cases.json': write('core_50_cases.json', cases),
    'core_50_summaries.json': write('core_50_summaries.json', summaries),
    'core_50_target_audit.json': write('core_50_target_audit.json', audit),
    'core_50_evaluation_dataset.json': write('core_50_evaluation_dataset.json', spec),
}
release = read('release_manifest.json')
release['files_sha256'].update(hashes)
(D / 'release_manifest.json').write_text(
    json.dumps(release, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('core50', spec['dataset']['labels'], spec['dataset']['date_min'], spec['dataset']['date_max'])
