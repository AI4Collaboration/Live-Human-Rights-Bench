# Review follow-up status

The [analysis directory](../analysis/README.md) is the index of completed work.
New model runs are on hold. The [experiment plan](NEXT_EXPERIMENTS.md) is the
single source for future conditions, prompts and budgets.

## Completed using existing data

| Review question | Evidence |
| --- | --- |
| Do conclusions depend on score thresholds? | [Five-rule threshold sensitivity](../analysis/threshold_sensitivity/REPORT.md) |
| Do continuous scores tell the same story? | [Paired Brier-score analysis](../analysis/review_offline/REPORT.md) |
| Which comparisons survive multiplicity adjustment? | [Prespecified comparison families](../analysis/review_followup/OFFLINE_PROTOCOL.md) and [results](../analysis/review_offline/REPORT.md) |
| How much change comes from ordinary sampling? | [Equal-size saved-rating comparisons](../analysis/reliability_controls/REPORT.md) |
| When do errors arise, recover or persist? | [Failure modes](../analysis/failure_modes/REPORT.md) and [finer analyses](../analysis/fine_grained_failures/REPORT.md) |
| Do cues preserve errors as well as correct answers? | [Correctness-stratified cue comparisons](../analysis/reliability_controls/REPORT.md) |
| Does generator/evaluator overlap explain the pattern? | [Evaluator exclusions with inputs fixed](../analysis/generator_exclusion/REPORT.md) |
| Can literal country substitutions create incoherent inputs? | [Context audit and screened comparisons](../analysis/stateswap_context/REPORT.md) |
| Does explanation length account for evaluation-language counts? | [Full-text paired CoT analysis](../analysis/reasoning_traces/full_text/README.md) |
| What has been checked by humans? | [Paragraph-link validation](ANNOTATION.md); this is separate from automated claim-retention assessment |
| Do current inputs match the reviewed sources? | [Source-binding evidence](../analysis/review_followup/input_evidence.json) |
| What do model knowledge dates tell us? | [Earlier-model time-window analysis](../analysis/model_time_windows/REPORT.md) |

## Remaining experiments

The retained plan has **three conditions and 25,398 target replies** across
GPT-5.6-sol, Claude Opus 4.6 and DeepSeek V4 Flash:

1. Neutral reassessment without an opposing opinion.
2. Neutral framing with the AI researcher identity fixed.
3. Explicit evaluation framing with the same identity and opposing challenge.

No cue and AI safety researcher are saved references. The standalone AI
researcher comparison is [rebuttal-only](REBUTTAL_EXPERIMENTS.md), not part of
this budget. Full-cohort repetitions require a separate decision. New generators,
confirming challenges, judge roles and applicant-identity runs are not scheduled.
Already published controls remain available in the
[control analysis](../analysis/september_controls/REPORT.md).

## Release follow-up

Publish the original generated paraphrases and claim-level summary-coverage
checkpoints when available, with hashes matching the actual experiment inputs.
The [data inventory](../data/README.md#inputs-awaiting-publication) records their
status. Publish missing historical dialogue logs only if the originals exist;
newly generated messages would not reconstruct the old conversations.

Prior literature retrieval evidence is retained in
[the source record](../analysis/review_followup/review_literature_20260920.json).
