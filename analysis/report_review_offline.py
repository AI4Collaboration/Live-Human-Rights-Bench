"""Independently check saved point estimates and write the review analysis report."""
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from statistics import fmean

from analyze_reliability_controls import GitSource, MODELS
from analyze_model_time_windows import OLD
from analyze_threshold_sensitivity import load_conversations, PRIMARY_N

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'analysis/review_offline'
manifest = json.loads((OUT / 'manifest.json').read_text())
for name, sha in manifest['outputs'].items():
    assert hashlib.sha256((OUT / name).read_bytes()).hexdigest() == sha
assert hashlib.sha256((ROOT / 'analysis/analyze_review_offline.py').read_bytes().replace(b'\r\n', b'\n')).hexdigest() == manifest['analysis_sha256']


def read(name):
    with (OUT / (name + '.csv')).open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def squared_error(score, violation):
    # Compute in score units from the reference, without the analysis loss function.
    distance = (100 - score) if violation else score
    return distance * distance / 10000


def check(row, before, after, truth):
    pairs = [(b, a, y) for b, a, y in zip(before, after, truth)
             if b is not None and a is not None and math.isfinite(b) and math.isfinite(a)]
    assert len(pairs) == int(row['paired_valid_n'])
    for field, index in [('before_brier', 0), ('after_brier', 1)]:
        value = fmean(squared_error(p[index], p[2]) for p in pairs)
        assert math.isclose(value, float(row[field]), abs_tol=1e-12), (row, field, value)
    assert math.isclose(float(row['change']), float(row['after_brier']) - float(row['before_brier']), abs_tol=1e-12)


source = GitSource(ROOT, manifest['source_revision'])
cases = source.json('data/processed/echr_unified.json')
truth = {(c['item_id'], str(c['article_full'])): c['violation_label'] == 'violation' for c in cases}
systematic = read('systematic_brier')
for model, _, directory in MODELS + OLD:
    old = model in {m for m, _, _ in OLD}
    arms = {}
    for arm in ['baseline', 'rq1']:
        folder = 'unified_fullcase_oldmodels' if old else 'unified_fullcase_latest'
        raw = list(source.jsonl(f'data/experiments/{folder}/{directory}/{arm}.jsonl'))
        arms[arm] = {(r['item_id'], str(r['article_full'])): r['avg_rating'] for r in raw}
        assert len(raw) == len(arms[arm]) == 1000
    folder = 'paraphrase_oldmodels' if old else 'paraphrase'
    raw = list(source.jsonl(f'data/experiments/{folder}/{model.replace("/", "_")}/paraphrase_results.jsonl'))
    for arm in ['original', 'light', 'medium', 'heavy']:
        arms[arm] = {(r['item_id'], str(r['article'])): r['avg_rating'] for r in raw if r['arm'] == arm}
        assert len(arms[arm]) == 1000
    for row in [r for r in systematic if r['model'] == model]:
        a, b = ('baseline', 'rq1') if row['condition'] == 'summary' else ('original', row['condition'])
        keys = sorted(truth)
        check(row, [arms[a][k] for k in keys], [arms[b][k] for k in keys], [truth[k] for k in keys])

initial, paths, _ = load_conversations(source, cases)
dialogue = read('dialogue_brier')
for i, (model, _, _) in enumerate(MODELS):
    keys = sorted((item, article, cond) for m, item, article, cond, mode in paths
                  if m == model and mode == 'static' and (m, item, article, cond, 'adaptive') in paths)
    assert len(keys) == PRIMARY_N[i]
    for row in [r for r in dialogue if r['model'] == model]:
        check(row, [initial[model, *k[:2]][0] for k in keys],
              [paths[model, *k, row['mode']][int(row['turn']) - 1] for k in keys],
              [initial[model, *k[:2]][1] == 1 for k in keys])
for path, record in source.inputs.items():
    assert record == manifest['inputs'][path], path

mult = read('multiplicity')
assert Counter(r['family'] for r in mult) == manifest['families']
for r in mult:
    assert float(r['simultaneous_lower']) <= float(r['lower_95']) <= float(r['upper_95']) <= float(r['simultaneous_upper'])
    if r['family'] == 'dialogue_brier':
        d = next(d for d in dialogue if d['model'] == r['model'] and d['turn'] == '3' and r['contrast'].startswith(d['mode']))
        assert d['cohort_sha256'] == r['cohort_sha256']
        assert math.isclose(float(d['change']), float(r['estimate']), abs_tol=1e-12)
for r in read('turn_descriptors'):
    assert sum(int(r[k]) for k in ['first_turn_1_n', 'first_turn_2_n', 'first_turn_3_n', 'no_reversal_n']) == int(r['n'])
validation = dict(status='passed', raw_systematic_point_estimates_verified=len(systematic),
                  dialogue_point_estimates_verified=len(dialogue), output_checksums_verified=len(manifest['outputs']),
                  input_hashes_rechecked=len(source.inputs), multiplicity_family_sizes_verified=True,
                  cohort_linkage_verified=True, turn_category_counts_verified=True,
                  scope='Raw stored means independently rescored in scalar arithmetic; dialogue means checked on the published cohorts. Bootstrap intervals use the documented analysis, not a separate resampling implementation.')
(OUT / 'validation.json').write_text(json.dumps(validation, indent=2) + '\n')


def ci(r):
    return f"{float(r['change']):+.4f} [{float(r['lower_95']):+.4f}, {float(r['upper_95']):+.4f}]"


lines = ['# Offline review analyses', '',
         'All results reuse stored scores at GitHub revision `' + manifest['source_revision'] + '`. **No new model calls.**', '',
         '## Main findings', '',
         '- Final conversational Brier error increases by **0.1143-0.5442** across all six models and both modes. All twelve increases retain positive Bonferroni-adjusted bootstrap intervals.',
         '- Summary Brier changes span **-0.0059 to +0.0167** across eight models. Paraphrase changes span **-0.0125 to +0.0104**, without a common direction across strengths.',
         '- Five of six US likelihood shifts remain negative after within-family correction. Claude\'s estimate is -0.5924 likelihood points, with adjusted interval **[-1.2861, +0.0995]**. All twelve US-versus-Russia/Ukraine contrasts remain negative.',
         '- All six pressure-by-mode interactions and both researcher-induced model-gap increases retain positive adjusted intervals. The latter intervals are **[36.39, 50.43]** static and **[15.47, 30.66]** adaptive percentage points.', '',
         '## Probability-forecast error', '',
         'Brier error is `(score / 100 - reference)^2`, on a 0-1 scale. Positive changes indicate worse probability forecasts. Numeric scores in the abstention band are included. This is not a calibration-only measure.', '',
         '| Model | Summary change [95% CI] | Static dialogue change [95% CI] | Adaptive dialogue change [95% CI] |',
         '| --- | --- | --- | --- |']
for r in systematic:
    if r['condition'] != 'summary': continue
    ds = {d['mode']: d for d in dialogue if d['model'] == r['model'] and d['turn'] == '3'}
    lines.append('| ' + ' | '.join([r['label'], ci(r), ci(ds['static']) if ds else 'Not evaluated', ci(ds['adaptive']) if ds else 'Not evaluated']) + ' |')
lines += ['', 'All summary pairs number 1,000. Missing-score exclusions occur in paraphrase: DeepSeek V4 Pro retains 985/981/982 and V4 Flash 1,000/999/999 for light/medium/heavy; all other model-strength pairs retain 1,000. Dialogue weights each of the 44,476 matched conditions equally, as in the main results.', '',
          '## Cue and turn descriptors', '',
          'On the shared 349 cases, the static researcher cue lowers final Brier error from 0.789 to 0.097 for Claude and from 0.833 to 0.388 for GPT. Adaptive values change from 0.627 to 0.105 and from 0.733 to 0.268, respectively. These aggregate improvements coexist with preservation of some initial errors.', '',
          'First reversal is the earliest opposite decisive verdict at turn 1, 2 or 3. No reversal is a separate outcome, not an imputed fourth turn. Adjacent switch counts require direct violation/no-violation transitions; abstention transitions are excluded and any abstention is counted separately. These descriptors do not require initially correct answers.', '',
          '## Sources and uncertainty', '',
          '- [Fixed analysis protocol](../review_followup/OFFLINE_PROTOCOL.md): five families, specified before computation.',
          '- [Systematic scores](systematic_brier.csv), [all dialogue turns](dialogue_brier.csv), [cue scores](cue_brier.csv), [paired cue changes](cue_brier_contrasts.csv), [turn descriptors](turn_descriptors.csv).',
          '- [Multiple-comparison intervals](multiplicity.csv): 38 contrasts, 20,000 judgment-cluster draws; Bonferroni-adjusted percentile bounds with nominal 95% coverage within each family. Pointwise Brier intervals use 2,000 draws. All use seed 731.',
          '- [Manifest](manifest.json) binds immutable input bytes and generated tables. [Validation](validation.json) independently recomputes scalar point estimates, checks counts, cohorts, family sizes and hashes.', '',
          'State Swap receives no Brier score against the original reference: changing jurisdiction does not supply a new ground-truth outcome. Repeated conditions are retained within judgment clusters; they are not independent cases.', '',
          '## Reproduce', '', '```text', 'python analysis/analyze_review_offline.py', 'python analysis/report_review_offline.py', '```', '']
(OUT / 'REPORT.md').write_text('\n'.join(lines), encoding='utf-8')
print(json.dumps(validation))
