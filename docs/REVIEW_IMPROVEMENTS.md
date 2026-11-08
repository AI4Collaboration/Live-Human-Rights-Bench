# Review follow-up status

The [analysis directory](../analysis/README.md) is the index of completed work.
The [November rebuttal package](rebuttal/README.md) maps every official review
point to a response and evidence. Its focused control study replaces the earlier
full-cohort plan. [New-release work](rebuttal/DELEGATED_TASKS.md) is assigned separately.

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

## Current controls and release follow-up

The [focused protocol](rebuttal/EXPERIMENTS.md) covers repetition variability,
opinion-only challenges, neutral reassessment and explicit evaluation framing.
Its [rebuttal index](rebuttal/README.md) records completion and results.

The generated paraphrases and independent verifier records are public. Recover
the remaining original summary-coverage checkpoints and historical adaptive
messages if retained elsewhere. New generations cannot reconstruct those records.
