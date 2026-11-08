# Rebuttal analyses

All new experiments use the frozen 50-judgment sample. The remaining analyses use existing records.

## Opposing opinions have an effect beyond neutral reassessment

These opinions assert the opposite verdict without asking for a changed answer. The formatting request is identical in every condition.

| Model | Shared cases | Neutral reassessment | Opinion only |
| --- | ---: | ---: | ---: |
| Opus-4.6 | 50 | 1/50 (2.0%) | 13/50 (26.0%) |
| 5.6-Sol | 46 | 1/46 (2.2%) | 12/46 (26.1%) |
| V4-Flash | 40 | 1/40 (2.5%) | 23/40 (57.5%) |

Challenges containing explicit demands to adopt the opposite verdict produce higher reversal rates. On the separately paired directive-versus-opinion cohorts the rates are 90.0% versus 26.0% for Opus-4.6, 89.6% versus 29.2% for 5.6-Sol, and 100.0% versus 58.5% for V4-Flash. Those comparisons use 50, 48 and 41 cases respectively. The contrast removes the replacement demand together with its confrontational wording. It separates opinion-only reversals from those under the original directive-containing challenge without isolating a training mechanism.

## Evaluation wording changes 5.6-Sol's response with identity held fixed

Both conditions introduce the challenger as an AI researcher. Only a six-word first-turn sentence changes.

| Model | Shared cases | Neutral framing | Evaluation framing | Difference in reversal rate [95% interval] |
| --- | ---: | ---: | ---: | ---: |
| Opus-4.6 | 50 | 1/50 (2.0%) | 1/50 (2.0%) | 0.0 [0.0, 0.0] |
| 5.6-Sol | 49 | 30/49 (61.2%) | 19/49 (38.8%) | -22.4 [-36.7, -10.2] |
| V4-Flash | 47 | 46/47 (97.9%) | 46/47 (97.9%) | 0.0 [-6.4, 6.4] |

Differences subtract the two rates expressed as percentages. The explicit evaluation sentence reduces reversal for 5.6-Sol. Opus-4.6 is already at 1/50 under neutral framing, leaving little room for a reduction. V4-Flash remains highly reversible. The Opus result is a floor observation, not evidence that evaluation awareness is absent. This intervention establishes sensitivity to evaluation wording, not a latent causal mechanism.

## Repetitions preserve the cue ordering but reveal case-level variation

The same initial reply starts three independent conversations per reference condition. The complete comparison requires all six conversations for a case.

| Model | Cue | Cases | Final reversal in repeats 1 / 2 / 3 | Mean | Cases with different reversal outcomes |
| --- | --- | ---: | ---: | ---: | ---: |
| Opus-4.6 | No cue | 48 | 91.7 / 93.8 / 95.8% | 93.8% | 2/48 (4.2%) |
| Opus-4.6 | AI safety researcher | 48 | 2.1 / 2.1 / 2.1% | 2.1% | 0/48 (0.0%) |
| 5.6-Sol | No cue | 49 | 89.8 / 89.8 / 89.8% | 89.8% | 5/49 (10.2%) |
| 5.6-Sol | AI safety researcher | 49 | 34.7 / 32.7 / 42.9% | 36.7% | 11/49 (22.4%) |

The Opus comparison contains 144 trajectories per condition and the Sol comparison contains 147. Three identical aggregate no-cue rates for Sol still hide changes in which five cases reverse. The researcher cue changes the reversal outcome across repeats for 11 of 49 Sol cases. Large average cue effects therefore coexist with instance-level sampling variability. The intervals in `new_controls/repetition_variation.csv` resample cases and then repetitions; they do not treat trajectories as independent new cases.

## The paraphrase result survives a fact-preservation filter

An independent Qwen3-235B verifier checks 69,106 claim-target pairs. Repaired paraphrases retain 99.2–99.5% of originally supported sampled claims. The verifier rejects 256 of 300 controls with deliberately swapped attributes. Without looking at target-model outcomes, we select 540 targets from 521 judgments where all sampled claims supported in the original remain supported in every rewrite. The selected targets have a median of 76 supported claims. Judgment-change rates remain 4.8–15.4% across the five primary models and three strengths. The filter covers sampled claims; it is not a human certification of the entire text.

Exact counts, intervals and missing-score counts are in [paraphrase_sensitivity.csv](existing/paraphrase_sensitivity.csv). Accuracy and change use the same target denominator within each scope. The 1,000-target repaired analysis and this 540-target sensitivity are separate.

## Reasoning evidence remains descriptive

The full-text analysis measures expressed references to evaluation. In the existing reasoning run, V4-Flash reverses in 125/201 researcher-cue explanations that mention evaluation. Opus also has nonrandom text availability: all 177 first-turn no-cue responses without explanations reverse, compared with 653/734 with explanations. Paired language comparisons retain the same cases with available text across cues. These processed explanations do not establish why a judgment changes.

## Release checks and the remaining empirical gap

All three designated v1.0 input hashes match the frozen release manifest. An offline chronological reconstruction merges 943 pre-2026 targets with the 57 v1.0 targets from 2026 and preserves every earlier record. This verifies existing-release consistency. Evaluation of genuinely new judgments remains a [separate task](../../docs/rebuttal/DELEGATED_TASKS.md).

## Coverage, cost and reproducibility

All 1,300 planned trajectories were attempted. There are 3,876 recorded requests and 1,275 complete three-turn trajectories. Twenty-six requests have no parsed score, including three timeouts. Later calls after an empty or failed reply were not sent. Incomplete trajectories are retained in the released records and excluded only from their explicitly defined comparisons. Missing-case bounds appear in `new_controls/condition_rates.csv`.

The key's observed usage increased by **$23.33**. Successful responses report $23.303998; the local ledger charges $23.488342 after conservatively reserving for timeouts. The execution ceiling was $50. No more paid experiments are scheduled in this package.

The audit passed 31,008 checks against saved messages and responses. It verifies initial replay, target identity, prompt hashes, score parsing, decoding requests and unique call IDs. The [protocol](../../docs/rebuttal/EXPERIMENTS.md) and [raw run](../../data/experiments/rebuttal_20261107/) retain the full collection record.

```bash
python analysis/analyze_rebuttal_existing.py
python analysis/analyze_rebuttal_controls.py
python analysis/build_rebuttal_report.py
```
