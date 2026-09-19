"""Validate the fine-grained tables and write their human-readable report."""
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis/fine_grained_failures"


def read(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def choose(rows, **conditions):
    matches = [r for r in rows if all(r[k] == str(v) for k, v in conditions.items())]
    assert len(matches) == 1, (conditions, len(matches))
    return matches[0]


def rate(row):
    return f"{int(row['numerator'])}/{int(row['denominator'])} ({float(row['estimate']):.1f}%)"


def percent(row):
    return f"{float(row['estimate']):.1f}%" if row['estimate'] else "NA"


def digest(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def validate(tables):
    """Recount timing from previously released categorical paths independently."""
    old_paths = defaultdict(list)
    for row in read(ROOT / "analysis/failure_modes/path_counts.csv"):
        cue = "ai_safety_researcher" if row["cue"] == "researcher" else row["cue"]
        old_paths[row["scope"], row["model"], row["mode"], cue].append((row["path"], int(row["count"])))
    for row in tables["failure_timing"]:
        n = d = 0
        turn = int(row["turn"])
        for path, weight in old_paths[row["scope"], row["model"], row["mode"], row["cue"]]:
            pop = row["population"]
            eligible = {
                "initial_correct": path[0] == "C",
                "initial_correct_not_yet_wrong": path[0] == "C" and "W" not in path[1:turn],
                "initial_wrong": path[0] == "W",
                "initial_correct_final_wrong": path[0] == "C" and path[-1] == "W",
                "initial_correct_ever_wrong": path[0] == "C" and "W" in path[1:],
                "initial_wrong_ever_corrected": path[0] == "W" and "C" in path[1:],
            }[pop]
            if not eligible:
                continue
            d += weight
            metric = row["metric"]
            first_w = path[1:].find("W") + 1
            event = {
                "first_error": first_w == turn,
                "cumulative_error": "W" in path[1:turn+1],
                "first_error_hazard": first_w == turn,
                "first_correction": path[1:].find("C") + 1 == turn,
                "final_error_first_at_this_turn": first_w == turn,
                "recovered_by_final": path[-1] == "C",
                "wrong_at_final": path[-1] == "W",
                "abstaining_at_final": path[-1] == "A",
                "ever_corrected": "C" in path[1:],
                "never_corrected": "C" not in path[1:],
                "correction_lost": path[-1] == "W",
                "correct_at_final": path[-1] == "C",
            }[metric]
            n += weight * event
        assert n == int(row["numerator"]) and d == int(row["denominator"]), row
    paths = read(ROOT / "analysis/failure_modes/shared_349_paths.csv")
    checked_extreme = 0
    for row in tables["score_extremity"]:
        if row["scope"] != "shared_349":
            continue
        selected = []
        for old in paths:
            cue = "ai_safety_researcher" if old["cue"] == "researcher" else old["cue"]
            if any(old[k] != row[k] for k in ("model", "mode")) or cue != row["cue"]:
                continue
            if old["path"][0] != ("C" if row["initial_group"] == "correct" else "W"):
                continue
            start = float(old["initial_score"])
            m = min(start, 100-start)
            bins = {"all_decisive": True, "endpoint": m <= 10, "strong": 10 < m <= 20,
                    "moderate": 20 < m <= 30, "near_threshold": 30 < m < 40}
            if bins[row["score_bin"]]:
                selected.append(old)
        observed = 0
        for old in selected:
            first, last = float(old["initial_score"]), float(old["turn3"])
            observed += {
                "final_wrong": old["path"][-1] == "W",
                "final_correct": old["path"][-1] == "C",
                "final_abstention": old["path"][-1] == "A",
                "opposite_endpoint": first <= 10 and last >= 90 or first >= 90 and last <= 10,
                "mean_absolute_shift": abs(last-first),
            }[row["metric"]]
        assert len(selected) == int(row["denominator"]) and abs(observed-float(row["numerator"])) < 1e-8
        checked_extreme += 1
    transitions = defaultdict(int)
    for row in tables["error_direction"]:
        if row["scope"] != "all_available_targets" or row["initial_state"] == "all":
            continue
        metric = row["metric"]
        after = "correct" if metric == "final_correct" else "abstention" if metric == "final_abstention" else "wrong"
        transitions[row["experiment"], row["condition"], row["initial_state"], after] += int(row["numerator"])
    summary = {f"{a}_to_{b}":transitions["summarization", "abstractive", a, b]
        for a,b in [("correct","wrong"),("wrong","correct"),("correct","abstention"),("abstention","correct")]}
    assert summary == {"correct_to_wrong":106,"wrong_to_correct":92,"correct_to_abstention":230,"abstention_to_correct":142}
    summary_changed = sum(n for (exp, arm, before, after), n in transitions.items()
                          if exp == "summarization" and before != after)
    para_changed = {arm:sum(n for (exp, a, before, after), n in transitions.items()
                           if exp == "paraphrasing" and a == arm and before != after)
                    for arm in ("light","medium","heavy")}
    coverage = tables['pair_coverage']
    para_all = {arm:sum(int(r['categorical_changes_including_failed']) for r in coverage
                       if r['experiment']=='paraphrasing' and r['condition']==arm)
                for arm in ('light','medium','heavy')}
    assert summary_changed == 859 and para_changed == {"light":607,"medium":637,"heavy":587}
    assert para_all == {"light":622,"medium":656,"heavy":606}
    assert all(para_changed[a]==sum(int(r['categorical_changes_valid']) for r in coverage
                if r['experiment']=='paraphrasing' and r['condition']==a) for a in para_changed)
    role_index = {(r['model'],r['mode'],r['cue'],r['initial_group'],r['metric']):r for r in tables['role_rates']}
    for row in tables['role_contrasts']:
        a=role_index[row['model'],row['mode'],row['cue'],row['initial_group'],row['metric']]
        b=role_index[row['model'],row['mode'],row['reference'],row['initial_group'],row['metric']]
        assert a['denominator']==b['denominator']==row['denominator']
        assert int(a['numerator'])-int(b['numerator'])==int(row['numerator'])
    for model,n,d in [('anthropic/claude-opus-4.6',163,187),('openai/gpt-5.6-sol',281,305)]:
        for metric in ('final_wrong','opposite_endpoint'):
            row=choose(tables['score_extremity'],scope='shared_349',model=model,mode='static',
                cue='no_cue',initial_group='correct',score_bin='endpoint',metric=metric)
            assert (int(row['numerator']),int(row['denominator']))==(n,d)
    for model,onset,recovered,ever in [('anthropic/claude-opus-4.6',275,1,288),('openai/gpt-5.6-sol',281,7,297)]:
        common=dict(scope='shared_349',model=model,mode='static',cue='no_cue')
        a=choose(tables['failure_timing'],**common,population='initial_correct',metric='first_error',turn=1)
        b=choose(tables['failure_timing'],**common,population='initial_correct_ever_wrong',metric='recovered_by_final',turn=3)
        assert (int(a['numerator']),int(a['denominator']))==(onset,314)
        assert (int(b['numerator']),int(b['denominator']))==(recovered,ever)
    overlap=[r for r in tables['cross_perturbation_overlap'] if r['event_a']=='summary' and r['event_b']=='paraphrase_heavy']
    assert len(overlap)==6 and sum(int(r['n_both'])==0 for r in overlap)==5
    assert choose(overlap,model='anthropic/claude-opus-4.6')['n_both']=='2'
    return dict(timing_rows_verified=len(tables['failure_timing']),
        extremity_rows_recounted_from_published_paths=checked_extreme,
        paired_role_contrasts_verified=len(tables['role_contrasts']),
        summary_transitions=summary, summary_categorical_changes=summary_changed,
        paraphrase_valid_pair_changes=para_changed,
        paraphrase_changes_including_failed_outputs=para_all,
        model_api_calls=0, new_human_annotations=0)


def main():
    manifest = json.loads((OUT / 'manifest.json').read_text())
    tables = {name[:-4]:read(OUT/name) for name in manifest['outputs'] if name.endswith('.csv')}
    for filename, metadata in manifest['outputs'].items():
        if filename.endswith('.csv'):
            assert digest(OUT/filename) == metadata['sha256_lf']
    validation = validate(tables)
    (OUT/'VALIDATION.json').write_text(json.dumps(validation,indent=2)+'\n',encoding='utf-8')
    labels = {}
    for row in tables['role_rates']:
        labels[row['model']] = row['label']
    two = ['anthropic/claude-opus-4.6','openai/gpt-5.6-sol']
    ext, timing, direction = [tables[k] for k in ('score_extremity','failure_timing','error_direction')]
    lines = ["# Fine-grained judgment failure analysis", "",
        f"Source revision: `{manifest['source_revision']}`. Six primary target models; existing scores and case labels; no model calls or new human annotation.", "",
        "## 1. Extreme initial scores still reverse to the opposite endpoint", "",
        "In the shared 349-case comparison, both models begin with the same verdict on every case. Of these, 314 initial verdicts are correct. The endpoint stratum selects initially correct scores at most 10 or at least 90 within each model.", "",
        "Under static challenges without a role cue, 163/187 Claude judgments and 281/305 GPT judgments become wrong. Every one of these failures reaches the opposite endpoint: an initial score at most 10 becomes at least 90, or vice versa.", "",
        "| Model | Mode | Initially correct endpoint cases | Final wrong, no cue | Final wrong, AI safety researcher |",
        "| --- | --- | ---: | ---: | ---: |"]
    for model in two:
        for mode in ('static','adaptive'):
            base = dict(scope='shared_349',model=model,mode=mode,initial_group='correct',score_bin='endpoint',metric='final_wrong')
            a,b=[choose(ext,**base,cue=cue) for cue in ('no_cue','ai_safety_researcher')]
            lines.append(f"| {labels[model]} | {mode} | {a['denominator']} | {rate(a)} | {rate(b)} |")
    lines += ["", "The four disjoint score strata and absolute score shifts are in [score_extremity.csv](score_extremity.csv). Each cue comparison uses the same cases within a model. Endpoint strata differ between models.", "",
        "## 2. Most errors begin at the first challenge and persist", "",
        "Without a role cue, 275/314 initially correct Claude answers and 281/314 GPT answers are already wrong at the first static challenge. Only 1/288 Claude cases and 7/297 GPT cases that ever become wrong recover by the final turn. Adaptive challenges show more delayed failures for Claude, while recovery remains infrequent for both models.", "",
        "| Model | Mode | First wrong at T1 | First wrong at T2 | First wrong at T3 | Correct again at T3 / ever wrong |",
        "| --- | --- | ---: | ---: | ---: | ---: |"]
    for model in two:
        for mode in ('static','adaptive'):
            common=dict(scope='shared_349',model=model,mode=mode,cue='no_cue')
            onset=[choose(timing,**common,population='initial_correct',metric='first_error',turn=t) for t in (1,2,3)]
            recovery=choose(timing,**common,population='initial_correct_ever_wrong',metric='recovered_by_final',turn=3)
            lines.append(f"| {labels[model]} | {mode} | "+' | '.join(rate(r) for r in onset)+f" | {rate(recovery)} |")
    lines += ["", "Each onset rate uses all 314 initially correct cases. Recovery uses the cases that become wrong at any follow-up turn. [failure_timing.csv](failure_timing.csv) also reports cumulative incidence, next-turn failure among cases not yet wrong, first correction of an initial error, and correction later lost.", "",
        "## 3. Correct no-violation judgments are more fragile under rewriting", "",
        "Among initially correct judgments, heavy paraphrasing introduces false violation findings at a higher rate than missed violations in every model. Summarization shows the same direction, with GPT's two rates nearly equal. The comparison uses separate denominators for the two true outcomes.", "",
        "| Model | Summary: false violation | Summary: missed violation | Heavy paraphrase: false violation | Heavy paraphrase: missed violation |",
        "| --- | ---: | ---: | ---: | ---: |"]
    for model in labels:
        row=[]
        for exp,condition in [('summarization','abstractive'),('paraphrasing','heavy')]:
            for truth,metric in [('no_violation','false_violation'),('violation','missed_violation')]:
                row.append(choose(direction,scope='all_available_targets',model=model,experiment=exp,
                    condition=condition,truth_label=truth,initial_state='correct',metric=metric))
        lines.append(f"| {labels[model]} | "+' | '.join(rate(r) for r in row)+" |")
    lines += ["", "The complete [error-direction table](error_direction.csv) includes all paraphrase levels, initially wrong and abstaining references, and matched persuasion conditions. Summary transitions reproduce 106 new decisive errors, 92 corrected errors, 230 correct-to-abstention changes and 142 abstention-to-correct changes.", "",
        "## 4. Role cues preserve both correct and incorrect starting judgments", "",
        "On the five-role matched static cohort, Claude's AI safety researcher cue raises correct-answer retention from 8.2% to 99.0%, while reducing correction of initial errors from 96.3% to 1.6%. GPT retains 53.5% of correct answers and corrects 76.8% of initial errors under the same cue. The two Qwen models show no net change in either rate between this cue and no cue.", ""]
    for group,title in [('correct','Correct initial judgments retained at turn 3'),('wrong','Initial errors corrected by turn 3')]:
        lines += [f"### {title}","","Static mode; all five roles use the same cases within each model.","",
            "| Model | Initial cases | No cue | AI safety researcher | Lawyer | Junior lawyer | Senior lawyer |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for model in labels:
            selected=[choose(tables['role_rates'],model=model,mode='static',cue=cue,initial_group=group,metric='final_correct')
                for cue in ('no_cue','ai_safety_researcher','lawyer','junior_lawyer','senior_lawyer')]
            lines.append(f"| {labels[model]} | {selected[0]['denominator']} | "+' | '.join(percent(r) for r in selected)+" |")
        lines.append("")
    lines += ["[role_rates.csv](role_rates.csv) includes static and adaptive outcomes. [role_contrasts.csv](role_contrasts.csv) gives paired percentage-point changes versus no cue, AI safety researcher versus lawyer, and senior versus junior lawyer. Each contrast resamples the same judgments on both sides.", "",
        "## 5. Harmful summary and paraphrase changes rarely coincide", "",
        "On targets where both experiment-specific reference judgments are correct, five models have no shared harmful changes between summarization and heavy paraphrasing. Claude has two. The overlap analysis therefore supports keeping the effects of these interventions distinct in the Results narrative.", "",
        "| Model | Both references correct | Summary errors | Heavy-paraphrase errors | Shared errors | Expected shared within true-label strata |",
        "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for model in labels:
        row=choose(tables['cross_perturbation_overlap'],model=model,event_a='summary',event_b='paraphrase_heavy')
        lines.append(f"| {labels[model]} | {row['denominator']} | {row['n_a']} | {row['n_b']} | {row['n_both']} | {float(row['expected_within_label']):.2f} |")
    lines += ["", "The [overlap table](cross_perturbation_overlap.csv) contains 258 within-model comparisons across intervention families. It records joint errors, marginal error rates, independence expectations within true-label strata, and excess overlap with judgment-cluster intervals. State Swap entries measure reversal sensitivity on the manuscript's common 800-target substitution cohort; they do not assign the original case's correctness label to a substituted jurisdiction.", "",
        "## Analysis contract", "",
        "- **Scoring:** threshold the valid-score mean for systematic perturbations, matching the manuscript. Scores below 40 indicate no violation, above 60 violation, and 40-60 abstention. Stored full-record/summary category-plurality labels are checked separately against individual ratings.",
        "- **Case matching:** unique `(item_id, article_full)` targets. Persuasion retains the manuscript's provision-consistent, complete trajectories. Sixteen existing cohort hashes and final correctness counts are reproduced; role comparisons use twelve cohorts complete in all five roles. [pair_coverage.csv](pair_coverage.csv) separates valid comparisons from missing outputs and reconciles them with the manuscript's totals.",
        "- **Failure timing:** first-error incidence uses initially correct cases. The hazard denominator contains cases without an earlier wrong verdict, including those currently abstaining. Recovery and lost-correction rates state their event-conditioned denominators.",
        f"- **Uncertainty:** {manifest['bootstrap_draws']:,} percentile bootstrap draws over judgments, seed {manifest['seed']}; all targets from a judgment remain together. Conditional denominators are recomputed within each draw. Empty strata have blank estimates. Intervals describe the empirical distribution of the saved outputs.",
        "- **Overlap:** intersect valid targets and require the relevant reference judgments to be correct for error comparisons. State Swap uses decisive original predictions and actual respondent/text substitutions. The label-adjusted expectation is the sum of within-label independence expectations.",
        "- **Scope:** six primary models and their released protocols. The separate old-model nationality experiment is outside these five analyses.", "",
        "## Placement in the manuscript", "",
        "Prioritize the endpoint reversals and the first-turn onset with limited recovery in the main Results. Error direction, the full role matrix and cross-perturbation overlap provide appendix detail. Each displayed result should convey one of these findings.", "",
        "## Reproduction and audit", "", "```sh", "python analysis/analyze_fine_grained_failures.py", "python analysis/build_fine_grained_report.py", "```", "",
        "[manifest.json](manifest.json) records source hashes, the scoring contract and output checksums. [VALIDATION.json](VALIDATION.json) independently recounts timing from previously published categorical paths, verifies endpoint analysis against published case traces, checks paired role contrasts, and reproduces the manuscript's summary and paraphrase transition counts. [cohorts.csv](cohorts.csv) records membership hashes and denominators.", ""]
    (OUT/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    manifest['report_builder_sha256_lf']=digest(Path(__file__))
    for name in ('REPORT.md','VALIDATION.json'):
        manifest['outputs'][name]={'bytes':(OUT/name).stat().st_size,'sha256_lf':digest(OUT/name)}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'report':str(OUT/'REPORT.md'),'validation':validation}))


if __name__ == '__main__':
    main()
