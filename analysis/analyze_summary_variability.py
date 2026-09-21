"""Compare within-target score dispersion from saved full-record and summary ratings."""
from pathlib import Path
import csv
import hashlib
import json

import numpy as np
from analyze_reliability_controls import (
    GitSource, MODELS, REVISION, bootstrap_totals, bounds, finite, write_csv,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'analysis/summary_variability'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    source = GitSource(ROOT, REVISION)
    prior = list(csv.DictReader((ROOT / 'analysis/reliability_controls/sampling_variation.csv').open(encoding='utf-8')))
    prior_index = {(r['model'], r['metric']): r for r in prior}
    rows, exclusions = [], []
    for model, label, folder in MODELS:
        arms = [{r['target_id']: r for r in source.jsonl(
            f'data/experiments/unified_fullcase_latest/{folder}/{name}.jsonl')}
            for name in ('baseline', 'rq1')]
        assert len(arms[0]) == len(arms[1]) == 1000 and arms[0].keys() == arms[1].keys()
        values, clusters = [], []
        for target in sorted(arms[0]):
            full, summary = (arm[target] for arm in arms)
            assert all(full[key] == summary[key] for key in ('item_id', 'article_full', 'violation_label'))
            if not all(len(r['ratings']) == 10 and all(finite(s) for s in r['ratings']) for r in (full, summary)):
                exclusions.append({'model': model, 'target_id': target})
                continue
            fv, sv = (float(np.var(r['ratings'], ddof=1)) for r in (full, summary))
            fs, ss = np.sqrt(fv), np.sqrt(sv)
            values.append([1., fs, ss, ss-fs, fv, sv, sv-fv])
            clusters.append(full['item_id'])
        totals, bootstrap, judgments = bootstrap_totals(np.asarray(values), clusters, draws=2000, seed=731)
        row = dict(model=model, label=label, targets=len(values), judgments=judgments, ratings_per_arm=10)
        names = ['full_mean_sd', 'summary_mean_sd', 'sd_difference',
                 'full_mean_variance', 'summary_mean_variance', 'variance_difference']
        for i, name in enumerate(names, 1):
            row[name] = float(totals[i]/totals[0])
            row[name+'_lower_95'], row[name+'_upper_95'] = bounds(bootstrap[:, i]/bootstrap[:, 0])
        for new_name, prior_name in [('full_mean_sd', 'reference_rating_sd'), ('summary_mean_sd', 'summary_rating_sd')]:
            assert abs(row[new_name] - float(prior_index[model, prior_name]['estimate'])) < 1e-9
        rows.append(row)
    assert sum(r['targets'] for r in rows) == 5995 and len(exclusions) == 5
    write_csv(OUT / 'source_data.csv', rows)
    lines = ['# Within-target score variability', '',
        '**Summary score variance rises in two models and falls in four.** Only DeepSeek V4 Flash has an increase whose paired 95% interval excludes zero; DeepSeek V4 Pro and both Qwen models have decreases whose intervals exclude zero.', '',
        'We calculate the sample standard deviation and variance of the ten saved scores separately for each target and input. We then average over the same complete target pairs in both arms. This measures variation across repeated responses to one input, rather than variation across different cases.', '',
        '| Model | Targets | Full-record mean variance | Summary mean variance | Paired variance difference [95% CI] |',
        '| --- | ---: | ---: | ---: | ---: |']
    for r in rows:
        lines.append(f"| {r['label']} | {r['targets']} | {r['full_mean_variance']:.2f} | {r['summary_mean_variance']:.2f} | {r['variance_difference']:+.2f} [{r['variance_difference_lower_95']:+.2f}, {r['variance_difference_upper_95']:+.2f}] |")
    lines += ['', 'Variance uses squared score points. For comparison, the following table reports the mean within-target SD in score points. Averaging variances gives more weight to targets with large dispersion than averaging SDs.', '',
        '| Model | Targets | Full-record mean SD | Summary mean SD | Paired SD difference [95% CI] |',
        '| --- | ---: | ---: | ---: | ---: |']
    for r in rows:
        lines.append(f"| {r['label']} | {r['targets']} | {r['full_mean_sd']:.2f} | {r['summary_mean_sd']:.2f} | {r['sd_difference']:+.2f} [{r['sd_difference_lower_95']:+.2f}, {r['sd_difference_upper_95']:+.2f}] |")
    lines += ['', 'Scores use the 0-100 scale. Differences are summary minus full record. Intervals use 2,000 paired judgment-cluster bootstrap resamples, seed 731; targets from the same judgment stay together. Five pairs with one missing summary score are excluded, leaving 5,995 model-target pairs. Existing published mean-SD estimates are reproduced to numerical precision.', '',
        'The [source table](source_data.csv) includes variance estimates and paired intervals as well as standard deviations. The [input manifest](manifest.json) records immutable Git input hashes. No model API calls are made.', '',
        'The separate [five-score analysis](../reliability_controls/REPORT.md) compares categorical judgments at a common sample size and shows input changes beyond same-input sampling variation.', '',
        'Reproduce from the repository root: `python analysis/analyze_summary_variability.py`.']
    (OUT / 'REPORT.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    manifest = dict(source_revision=source.revision, model_api_calls=0, draws=2000, seed=731,
        input_units='Target-level sample SD and variance over ten ratings per input; paired comparison clustered by judgment.',
        inputs=source.inputs, exclusions=exclusions,
        script_sha256_lf=hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
        output_sha256_lf={name: hashlib.sha256((OUT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
                         for name in ('source_data.csv', 'REPORT.md')})
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    print(json.dumps([{'model':r['label'], 'sd_delta':round(r['sd_difference'],3),
        'sd_ci':[round(r['sd_difference_lower_95'],3),round(r['sd_difference_upper_95'],3)],
        'variance_delta':round(r['variance_difference'],3),
        'variance_ci':[round(r['variance_difference_lower_95'],3),round(r['variance_difference_upper_95'],3)]} for r in rows]))


if __name__ == '__main__':
    main()
