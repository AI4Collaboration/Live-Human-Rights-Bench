"""Saved-score review checks. No experiment runner or model client is imported."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

import numpy as np

from analyze_reliability_controls import (
    MODELS, ARMS, GitSource, bootstrap_totals, category, finite, ground_truth, write_csv,
)
from analyze_fine_grained_failures import load_scored_rows, state_swap_targets
from analyze_threshold_sensitivity import load_conversations, PRIMARY_N
from analyze_model_time_windows import OLD

REVISION = "c9ad289158fe3a244312a341c5863a075fbe19db"
FAMILIES = {
    "us_likelihood": 6, "us_destination_order": 12,
    "pressure_mode_interaction": 6, "shared_role_gap": 2,
    "dialogue_brier": 12,
}


def cohort(keys):
    return hashlib.sha256(json.dumps(sorted(keys), separators=(",", ":")).encode()).hexdigest()


def interval(values, alpha=.05):
    assert np.isfinite(values).all()
    return tuple(map(float, np.quantile(values, [alpha / 2, 1 - alpha / 2])))


def loss(scores, truth):
    scores = np.asarray(scores, float)
    truth = np.asarray(truth)
    assert np.isin(truth, [-1, 1]).all()
    return (scores / 100 - (truth + 1) / 2) ** 2


def paired(keys, before, after, truth, meta, draws=2000):
    before, after = np.asarray(before, float), np.asarray(after, float)
    valid = np.isfinite(before) & np.isfinite(after)
    selected = [k for k, use in zip(keys, valid) if use]
    b, a = loss(before[valid], truth[valid]), loss(after[valid], truth[valid])
    assert len(selected) and np.all((b >= 0) & (b <= 1)) and np.all((a >= 0) & (a <= 1))
    _, boots, n_judgments = bootstrap_totals(
        np.column_stack([b, a, a - b, np.ones(len(b))]), [k[0] for k in selected], draws, 731)
    delta_boot = boots[:, 2] / boots[:, 3]
    lo, hi = interval(delta_boot)
    row = dict(**meta, cohort_n=len(keys), paired_valid_n=len(selected),
        excluded_missing_n=int((~valid).sum()), judgments=n_judgments,
        before_abstention_n=int(np.sum((before[valid] >= 40) & (before[valid] <= 60))),
        after_abstention_n=int(np.sum((after[valid] >= 40) & (after[valid] <= 60))),
        before_brier=float(b.mean()), after_brier=float(a.mean()),
        change=float((a - b).mean()), lower_95=lo, upper_95=hi,
        cohort_sha256=cohort(selected))
    assert np.isclose(row['after_brier'] - row['before_brier'], row['change'])
    return row


def adjusted(keys, values, meta):
    values = np.asarray(values, float)
    assert np.isfinite(values).all() and len(keys) == len(values)
    _, boot, groups = bootstrap_totals(
        np.column_stack([values, np.ones(len(values))]), [k[0] for k in keys], 20000, 731)
    estimates = boot[:, 0] / boot[:, 1]
    lo, hi = interval(estimates)
    alo, ahi = interval(estimates, .05 / FAMILIES[meta['family']])
    return dict(**meta, n=len(keys), judgments=groups, estimate=float(values.mean()),
        lower_95=lo, upper_95=hi, family_size=FAMILIES[meta['family']],
        simultaneous_lower=alo, simultaneous_upper=ahi,
        excludes_zero=bool(alo > 0 or ahi < 0), cohort_sha256=cohort(keys))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument('--out', type=Path, default=Path(__file__).resolve().parent / 'review_offline')
    args = ap.parse_args(); args.out.mkdir(parents=True, exist_ok=True)
    source = GitSource(args.repo, REVISION)
    cases = source.json('data/processed/echr_unified.json')
    canonical = {(c['item_id'], str(c['article_full'])): c for c in cases}
    assert len(canonical) == 1000 and len({k[0] for k in canonical}) == 947
    keys = sorted(canonical)
    truth = np.array([ground_truth(canonical[k]['violation_label']) for k in keys])
    tables, checks = defaultdict(list), []
    # Each experiment's original arm remains separate.
    for model, label, directory in MODELS + OLD:
        older = model in {m for m, _, _ in OLD}
        folder = 'unified_fullcase_oldmodels' if older else 'unified_fullcase_latest'
        full = {}
        for name in ('baseline', 'rq1'):
            rows = load_scored_rows(source, f'data/experiments/{folder}/{directory}/{name}.jsonl', canonical, checks)
            full[name] = {k: v for (k, _), v in rows.items()}
        folder = 'paraphrase_oldmodels' if older else 'paraphrase'
        para = load_scored_rows(source, f'data/experiments/{folder}/{model.replace("/", "_")}/paraphrase_results.jsonl', canonical, checks)
        comparisons = [('summary', full['baseline'], full['rq1'])] + [
            (a, {k: v for (k, arm), v in para.items() if arm == 'original'},
                {k: v for (k, arm), v in para.items() if arm == a}) for a in ('light', 'medium', 'heavy')]
        for condition, before, after in comparisons:
            assert set(before) == set(after) == set(keys)
            tables['systematic_brier'].append(paired(keys,
                [before[k] for k in keys], [after[k] for k in keys], truth,
                dict(model=model, label=label, roster='earlier' if older else 'primary', condition=condition)))
        print('Scored summary and paraphrase:', label, flush=True)
    state_keys = sorted(state_swap_targets(source, canonical))
    for model, label, _ in MODELS:
        rows = load_scored_rows(source, f'data/experiments/stateswap_summary/{model.replace("/", "_")}/stateswap_summary_results.jsonl', canonical, checks)
        for right in ('original', 'Russia', 'Ukraine'):
            values = [rows[k, 'US'] - rows[k, right] for k in state_keys]
            tables['multiplicity'].append(adjusted(state_keys, values,
                dict(family='us_likelihood' if right == 'original' else 'us_destination_order',
                     model=model, contrast='US_minus_' + right, unit='likelihood_points')))
    initial, paths, counts = load_conversations(source, cases)
    for index, (model, label, _) in enumerate(MODELS):
        matched = sorted((item, article, cond) for m, item, article, cond, mode in paths
            if m == model and mode == 'static' and (m, item, article, cond, 'adaptive') in paths)
        assert len(matched) == PRIMARY_N[index]
        y = np.array([initial[model, *k[:2]][1] for k in matched])
        before = np.array([initial[model, *k[:2]][0] for k in matched])
        for mode in ARMS:
            after = np.array([paths[model, *k, mode] for k in matched])
            for turn in (1, 2, 3):
                tables['dialogue_brier'].append(paired(matched, before, after[:, turn-1], y,
                    dict(model=model, label=label, mode=mode, turn=turn)))
            tables['multiplicity'].append(adjusted(matched,
                loss(after[:, -1], y) - loss(before, y),
                dict(family='dialogue_brier', model=model, contrast=mode+'_final_minus_initial', unit='brier_0_1')))
            categories = np.column_stack([category(before), category(after)])
            reversed_at = categories[:, 1:] == -categories[:, :1]
            first = np.where(reversed_at.any(axis=1), reversed_at.argmax(axis=1)+1, 0)
            switches = (categories[:, 1:] * categories[:, :-1] == -1).sum(axis=1)
            tables['turn_descriptors'].append(dict(model=model, mode=mode, n=len(matched),
                first_turn_1_n=int(np.sum(first == 1)), first_turn_2_n=int(np.sum(first == 2)),
                first_turn_3_n=int(np.sum(first == 3)), no_reversal_n=int(np.sum(first == 0)),
                mean_adjacent_strict_switches=float(switches.mean()),
                any_abstention_n=int(np.sum(np.any(categories[:, 1:] == 0, axis=1))),
                cohort_sha256=cohort(matched)))
        pressure_keys = sorted((item, article) for m, item, article in initial if m == model and
            all((m, item, article, cond, mode) in paths for cond in ('baseline_low', 'baseline_high') for mode in ARMS))
        assert len(pressure_keys) == [556, 779, 178, 601, 624, 516][index]
        pressure = {}
        for cond in ('baseline_low', 'baseline_high'):
            for mode in ARMS:
                pressure[cond, mode] = np.array([int(category(paths[model, *k, cond, mode][-1]) ==
                    -category(initial[model, *k][0])) for k in pressure_keys])
        values = 100 * (pressure['baseline_high', 'adaptive']-pressure['baseline_low', 'adaptive']
                     -pressure['baseline_high', 'static']+pressure['baseline_low', 'static'])
        tables['multiplicity'].append(adjusted(pressure_keys, values,
            dict(family='pressure_mode_interaction', model=model, contrast='adaptive_minus_static_high_minus_low', unit='percentage_points')))
        print('Scored conversations:', label, flush=True)
    two = [m for m, _, _ in MODELS[:2]]
    shared = sorted(k for k in keys if all((m, *k, c, a) in paths
        for m in two for c in ('baseline_high', 'authority_researcher') for a in ARMS)
        and category(initial[two[0], *k][0]) == category(initial[two[1], *k][0]))
    assert len(shared) == len({k[0] for k in shared}) == 349
    cue_reversals = {}
    for model, label, _ in MODELS[:2]:
        before = np.array([initial[model, *k][0] for k in shared])
        y = np.array([initial[model, *k][1] for k in shared])
        assert np.sum(category(before) == y) == 314
        for mode in ARMS:
            finals = {}
            for cue in ('baseline_high', 'authority_researcher'):
                finals[cue] = np.array([paths[model, *k, cue, mode][-1] for k in shared])
                tables['cue_brier'].append(paired(shared, before, finals[cue], y,
                    dict(model=model, label=label, mode=mode, cue=cue)))
                cue_reversals[model, mode, cue] = (category(finals[cue]) == -category(before)).astype(int)
            tables['cue_brier_contrasts'].append(paired(shared, finals['baseline_high'], finals['authority_researcher'], y,
                dict(model=model, label=label, mode=mode, contrast='researcher_minus_no_cue')))
    for mode, expected in [('static', (318,323,1,158)), ('adaptive',(283,296,4,98))]:
        assert tuple(cue_reversals[m, mode, c].sum() for c in ('baseline_high','authority_researcher') for m in two) == expected
        values = 100 * (cue_reversals[two[1], mode, 'authority_researcher']-cue_reversals[two[0], mode, 'authority_researcher']
                     -cue_reversals[two[1], mode, 'baseline_high']+cue_reversals[two[0], mode, 'baseline_high'])
        tables['multiplicity'].append(adjusted(shared, values,
            dict(family='shared_role_gap', model='GPT_minus_Claude', contrast=mode+'_cue_gap_increase', unit='percentage_points')))
    assert sum(PRIMARY_N) == 44476
    for family, n in FAMILIES.items():
        assert sum(r['family'] == family for r in tables['multiplicity']) == n
    for name, rows in tables.items(): write_csv(args.out / (name + '.csv'), rows)
    fields = sorted({key for row in checks for key in row})
    write_csv(args.out / 'input_checks.csv', [{key: row.get(key, 0) for key in fields} for row in checks])
    manifest = dict(source_revision=source.revision, new_model_calls=0, seed=731,
        brier_draws=2000, multiplicity_draws=20000, families=FAMILIES,
        inputs=source.inputs, conversation_counts=counts,
        analysis_sha256=hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
        outputs={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in args.out.glob('*.csv')})
    (args.out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'systematic_comparisons':len(tables['systematic_brier']),
        'dialogue_turn_comparisons':len(tables['dialogue_brier']),
        'multiplicity_comparisons':len(tables['multiplicity']),
        'intervals_containing_zero':[r['model']+':'+r['contrast'] for r in tables['multiplicity'] if not r['excludes_zero']]}),flush=True)


if __name__ == '__main__': main()
