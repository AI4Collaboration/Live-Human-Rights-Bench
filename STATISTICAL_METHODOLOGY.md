# Statistical methodology for the current manuscript

This document describes the experiments in GitHub revision `78b775f` and the
manuscript analysis of those records. State Swap results were added in `cc59734`;
their input review is recorded below.

## Scores and predictions

Every score is a violation likelihood on the **0-100** scale:

| Score | Prediction |
| --- | --- |
| Below 40 | No violation |
| 40 through 60, inclusive | Abstention |
| Above 60 | Violation |

Section 4 requests ten scores per input and classifies their valid-score mean.
Full-record and summary checkpoints retain individual scores; published paraphrase
and State Swap
checkpoints retain `avg_rating`, a prediction and the unparsed count. An input
with no parsed score is a failed prediction.

The saved full-record/summary `prediction` fields instead use category plurality.
They remain unchanged in the raw data. The manuscript recomputes its primary
predictions from scores and reports plurality, with ties assigned to abstention,
as a sensitivity analysis. Section 5 applies the thresholds to each response's
single score.

## Correctness and paired comparisons

Accuracy is the proportion of all evaluated targets that match the Court outcome.
Abstentions and failures remain in the denominator. Balanced accuracy is the
mean recall of the violation and no-violation classes.

- **Summarization:** 1,000 full-record/summary pairs per model, six models.
- **Paraphrasing:** 1,000 pairs per model and rewriting level, each compared with
  its original arm under the paraphrase prompt. The six four-arm checkpoints
  contain 24,000 rows.
- **State Swap:** compare each country arm with the same target's original
  summary. The six four-arm checkpoints contain 24,000 rows.

A strict reversal crosses between violation and no violation. Abstention
transitions are counted separately. Accuracy differences are reported in
percentage points, using each experiment's matched reference.

## State Swap input review

The released replacement rule changes 891 US, 859 Russia and 725 Ukraine inputs
out of 1,000 targets per arm. Report actual text changes separately from
unchanged inputs, including original respondents already equal to the swap
destination. Pair comparisons within the State Swap experiment's own original
arm. Missing scores remain failures rather than abstentions or reversals.
The [protocol and input review](docs/STATESWAP.md) provide the counts and
published scoring convention.

## Three-turn persuasion

The 6,000 initial records contain 5,373 decided responses, 310 abstentions and
317 missing or invalid scores. Eleven conditions and two modes produce 118,206
saved branch records, including 105,780 complete three-turn trajectories.

Matching static and adaptive trajectories yields 47,033 complete pairs. The
primary analysis retains **44,476 provision-consistent pairs**, excluding
2,557 pairs associated with 53 targets from 49 judgments whose follow-up question
uses a different provision. The full matched cohort is a sensitivity analysis.

For every model, use this same primary cohort for turn-specific reversal,
any-turn reversal, final-turn reversal and correctness decomposition. Earlier-only
reversal is any-turn minus final-turn reversal. Correct-to-wrong rates divide by
initially correct responses; wrong-to-correct rates divide by initially wrong
responses. Overall accuracy uses all matched conditions, including abstentions.

Pressure interactions require complete low/high branches in both modes.
Cue contrasts match the relevant conditions on common targets. Their denominators
therefore differ from the pooled model comparison.

## Confidence intervals

The manuscript uses **2,000 bootstrap draws clustered by judgment**, with
**seed 731**. A sampled judgment brings all associated target observations into
the draw; paired arms, conditions and turns remain together. Conditional metrics
recompute their denominators in each draw. Report the 2.5th and 97.5th percentiles
as the 95% interval.

Complete-sample sensitivity requires every requested rating in both compared
arms to parse. The primary accuracy analysis retains all targets. This keeps
sampling failures distinct from predicted abstention and strict reversal.

## Fact-retention analysis

The selected coverage checkpoints compare both summary variants against the
same **51,347 sampled claims**, including **19,646 Court-referenced claims from
659 judgments**. Retention is supported claims divided by sampled claims in the
specified group.

To relate retention to prediction changes, average target/model change indicators
within each judgment, then compute Spearman correlation with that judgment's
Court-referenced retention. Resample judgments for its interval. Coverage
measures information retained; the paired prediction analysis measures judgment
changes.

The selected claim-level checkpoints are local analysis artifacts awaiting
publication. [README.md](README.md) records current data availability and runner
paths. The Overleaf manuscript's source manifests and aggregate tables pin the
reported estimates.
