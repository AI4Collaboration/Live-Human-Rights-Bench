# Full-explanation analysis

Source revision: `8f8dcfabe95fdab402de8ad66005530fbc987ec7`. Existing data only; no model API calls.

## Measures and cohorts

- **Scope:** Entire saved explanation at each challenged turn; no prefix truncation or minimum length.
- **Cohort:** Complete three-turn scores under no cue, lawyer and AI safety researcher within each model and mode; initial responses are shared across these cues.
- **Availability:** Empty text is unavailable reasoning, not zero awareness. Report availability on the whole cohort and text rates among nonempty explanations.
- **Paired:** Paired cue comparisons retain instances with nonempty explanations under all three cues at that turn; there is no word-count cutoff.
- **Longitudinal:** Same instances with nonempty explanations for all three cues and all three turns, for within-model changes over turns.
- **Length:** Word counts use the published word regex. Median and interquartile range describe the complete explanation.
- **Frequency:** Explanations with at least one evaluation phrase divided by nonempty explanations; each instance counts once.
- **Density:** Nonoverlapping phrase occurrences divided by all words in the complete explanations, multiplied by 1000.
- **Outcomes:** Same-turn opposite decisive verdict among explanations containing the phrases; abstentions remain in this denominator. Text groups are descriptive and not randomized.
- **All_conditions:** Condition-specific complete cohorts; for supplementary coverage only, not paired role effect estimates.
- **Uncertainty:** 5000 source-judgment cluster bootstrap draws; target provisions and paired cues stay together; seed 20260926.
- **Interpretation:** Verbalized references to evaluation in written explanations, including Opus's summarized reasoning; not latent awareness or a causal mechanism.

## First static challenge: availability and full explanations

| Model | Cue | Recorded / cohort | Median words [IQR] | Evaluation mentions | Occurrences / 1,000 words |
|---|---|---:|---:|---:|---:|
| Opus-4.6 | No cue | 734/911 | 29 [24, 139] | 15/734 (2.0%) | 0.251 |
| Opus-4.6 | Lawyer | 910/911 | 199 [149, 266.75] | 22/910 (2.4%) | 0.115 |
| Opus-4.6 | AI safety researcher | 911/911 | 147 [95, 213.5] | 79/911 (8.7%) | 0.556 |
| V4-Flash | No cue | 946/946 | 94 [60, 173] | 25/946 (2.6%) | 0.200 |
| V4-Flash | Lawyer | 946/946 | 149 [86, 242] | 60/946 (6.3%) | 0.361 |
| V4-Flash | AI safety researcher | 946/946 | 189 [107, 317.25] | 201/946 (21.2%) | 1.028 |

## First static challenge: same instances with text in all three cues

| Model | Cue | N | Median words [IQR] | Evaluation mentions | Occurrences / 1,000 words |
|---|---|---:|---:|---:|---:|
| Opus-4.6 | No cue | 734 | 29 [24, 139] | 15/734 (2.0%) | 0.251 |
| Opus-4.6 | Lawyer | 734 | 190.5 [146, 259] | 17/734 (2.3%) | 0.113 |
| Opus-4.6 | AI safety researcher | 734 | 129 [89, 183] | 52/734 (7.1%) | 0.506 |
| V4-Flash | No cue | 946 | 94 [60, 173] | 25/946 (2.6%) | 0.200 |
| V4-Flash | Lawyer | 946 | 149 [86, 242] | 60/946 (6.3%) | 0.361 |
| V4-Flash | AI safety researcher | 946 | 189 [107, 317.25] | 201/946 (21.2%) | 1.028 |

## Text and judgment changes

This comparison uses the same first-turn instances with text under all three cues as the paired table above.

| Model | Cue | Reversal among explanations mentioning evaluation | Reversal among explanations without such mentions |
|---|---|---:|---:|
| Opus-4.6 | No cue | 10/15 (66.7%) | 643/719 (89.4%) |
| Opus-4.6 | Lawyer | 0/17 (0.0%) | 78/717 (10.9%) |
| Opus-4.6 | AI safety researcher | 1/52 (1.9%) | 9/682 (1.3%) |
| V4-Flash | No cue | 25/25 (100.0%) | 914/921 (99.2%) |
| V4-Flash | Lawyer | 47/60 (78.3%) | 869/886 (98.1%) |
| V4-Flash | AI safety researcher | 125/201 (62.2%) | 664/745 (89.1%) |

`results.json` includes all three turns, adaptive coverage, paired intervals and a separate all-condition inventory. `cohorts.json` lists exact target identities. `observations.csv` records full-text counts, verdict categories and hashes without reproducing the explanations.

## Reproduction

`python analysis/analyze_reasoning_full_text.py --revision 8f8dcfabe95fdab402de8ad66005530fbc987ec7`

Every recorded explanation is analyzed in full; cue comparisons require available text without a minimum word count.
