# Fine-grained judgment failure analysis

Source revision: `775d68fba9146ac33e77b59cf72c288af13431f4`. Six primary target models; existing scores and case labels; no model calls or new human annotation.

## 1. Extreme initial scores still reverse to the opposite endpoint

In the shared 349-case comparison, both models begin with the same verdict on every case. Of these, 314 initial verdicts are correct. The endpoint stratum selects initially correct scores at most 10 or at least 90 within each model.

Under static challenges without a role cue, 163/187 Claude judgments and 281/305 GPT judgments become wrong. Every one of these failures reaches the opposite endpoint: an initial score at most 10 becomes at least 90, or vice versa.

| Model | Mode | Initially correct endpoint cases | Final wrong, no cue | Final wrong, AI safety researcher |
| --- | --- | ---: | ---: | ---: |
| Claude Opus 4.6 | static | 187 | 163/187 (87.2%) | 0/187 (0.0%) |
| Claude Opus 4.6 | adaptive | 187 | 139/187 (74.3%) | 0/187 (0.0%) |
| GPT-5.6-sol | static | 305 | 281/305 (92.1%) | 122/305 (40.0%) |
| GPT-5.6-sol | adaptive | 305 | 254/305 (83.3%) | 73/305 (23.9%) |

The four disjoint score strata and absolute score shifts are in [score_extremity.csv](score_extremity.csv). Each cue comparison uses the same cases within a model. Endpoint strata differ between models.

## 2. Most errors begin at the first challenge and persist

Without a role cue, 275/314 initially correct Claude answers and 281/314 GPT answers are already wrong at the first static challenge. Only 1/288 Claude cases and 7/297 GPT cases that ever become wrong recover by the final turn. Adaptive challenges show more delayed failures for Claude, while recovery remains infrequent for both models.

| Model | Mode | First wrong at T1 | First wrong at T2 | First wrong at T3 | Correct again at T3 / ever wrong |
| --- | --- | ---: | ---: | ---: | ---: |
| Claude Opus 4.6 | static | 275/314 (87.6%) | 10/314 (3.2%) | 3/314 (1.0%) | 1/288 (0.3%) |
| Claude Opus 4.6 | adaptive | 215/314 (68.5%) | 41/314 (13.1%) | 13/314 (4.1%) | 15/269 (5.6%) |
| GPT-5.6-sol | static | 281/314 (89.5%) | 11/314 (3.5%) | 5/314 (1.6%) | 7/297 (2.4%) |
| GPT-5.6-sol | adaptive | 256/314 (81.5%) | 17/314 (5.4%) | 3/314 (1.0%) | 13/276 (4.7%) |

Each onset rate uses all 314 initially correct cases. Recovery uses the cases that become wrong at any follow-up turn. [failure_timing.csv](failure_timing.csv) also reports cumulative incidence, next-turn failure among cases not yet wrong, first correction of an initial error, and correction later lost.

## 3. Correct no-violation judgments are more fragile under rewriting

Among initially correct judgments, heavy paraphrasing introduces false violation findings at a higher rate than missed violations in every model. Summarization shows the same direction, with GPT's two rates nearly equal. The comparison uses separate denominators for the two true outcomes.

| Model | Summary: false violation | Summary: missed violation | Heavy paraphrase: false violation | Heavy paraphrase: missed violation |
| --- | ---: | ---: | ---: | ---: |
| Claude Opus 4.6 | 14/100 (14.0%) | 10/647 (1.5%) | 8/105 (7.6%) | 3/648 (0.5%) |
| GPT-5.6-sol | 5/166 (3.0%) | 20/669 (3.0%) | 8/166 (4.8%) | 0/668 (0.0%) |
| DeepSeek V4 Pro | 8/95 (8.4%) | 6/632 (0.9%) | 8/111 (7.2%) | 6/623 (1.0%) |
| DeepSeek V4 Flash | 5/18 (27.8%) | 14/683 (2.0%) | 15/45 (33.3%) | 12/636 (1.9%) |
| Qwen3-235B | 5/66 (7.6%) | 2/597 (0.3%) | 1/62 (1.6%) | 2/607 (0.3%) |
| Qwen3-32B | 11/52 (21.2%) | 6/639 (0.9%) | 4/49 (8.2%) | 2/645 (0.3%) |

The complete [error-direction table](error_direction.csv) includes all paraphrase levels, initially wrong and abstaining references, and matched persuasion conditions. Summary transitions reproduce 106 new decisive errors, 92 corrected errors, 230 correct-to-abstention changes and 142 abstention-to-correct changes.

## 4. Role cues preserve both correct and incorrect starting judgments

On the five-role matched static cohort, Claude's AI safety researcher cue raises correct-answer retention from 8.2% to 99.0%, while reducing correction of initial errors from 96.3% to 1.6%. GPT retains 53.5% of correct answers and corrects 76.8% of initial errors under the same cue. The two Qwen models show no net change in either rate between this cue and no cue.

### Correct initial judgments retained at turn 3

Static mode; all five roles use the same cases within each model.

| Model | Initial cases | No cue | AI safety researcher | Lawyer | Junior lawyer | Senior lawyer |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Claude Opus 4.6 | 684 | 8.2% | 99.0% | 76.5% | 85.5% | 83.5% |
| GPT-5.6-sol | 776 | 8.5% | 53.5% | 21.5% | 24.7% | 25.0% |
| DeepSeek V4 Pro | 387 | 0.5% | 4.9% | 1.0% | 0.8% | 1.6% |
| DeepSeek V4 Flash | 615 | 1.1% | 5.9% | 1.5% | 2.6% | 2.8% |
| Qwen3-235B | 618 | 0.8% | 0.8% | 1.3% | 1.8% | 0.5% |
| Qwen3-32B | 603 | 0.2% | 0.2% | 0.0% | 0.2% | 0.2% |

### Initial errors corrected by turn 3

Static mode; all five roles use the same cases within each model.

| Model | Initial cases | No cue | AI safety researcher | Lawyer | Junior lawyer | Senior lawyer |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Claude Opus 4.6 | 190 | 96.3% | 1.6% | 48.9% | 31.1% | 36.8% |
| GPT-5.6-sol | 142 | 98.6% | 76.8% | 97.9% | 92.3% | 93.0% |
| DeepSeek V4 Pro | 120 | 100.0% | 93.3% | 99.2% | 99.2% | 97.5% |
| DeepSeek V4 Flash | 202 | 97.5% | 91.6% | 97.5% | 95.0% | 98.0% |
| Qwen3-235B | 205 | 98.0% | 98.0% | 97.6% | 98.0% | 99.0% |
| Qwen3-32B | 221 | 99.1% | 99.1% | 99.5% | 100.0% | 99.5% |

[role_rates.csv](role_rates.csv) includes static and adaptive outcomes. [role_contrasts.csv](role_contrasts.csv) gives paired percentage-point changes versus no cue, AI safety researcher versus lawyer, and senior versus junior lawyer. Each contrast resamples the same judgments on both sides.

## 5. Harmful summary and paraphrase changes rarely coincide

On targets where both experiment-specific reference judgments are correct, five models have no shared harmful changes between summarization and heavy paraphrasing. Claude has two. The overlap analysis therefore supports keeping the effects of these interventions distinct in the Results narrative.

| Model | Both references correct | Summary errors | Heavy-paraphrase errors | Shared errors | Expected shared within true-label strata |
| --- | ---: | ---: | ---: | ---: | ---: |
| Claude Opus 4.6 | 736 | 22 | 6 | 2 | 0.56 |
| GPT-5.6-sol | 824 | 21 | 5 | 0 | 0.12 |
| DeepSeek V4 Pro | 678 | 8 | 4 | 0 | 0.09 |
| DeepSeek V4 Flash | 634 | 8 | 12 | 0 | 0.14 |
| Qwen3-235B | 633 | 4 | 1 | 0 | 0.04 |
| Qwen3-32B | 666 | 10 | 1 | 0 | 0.21 |

The [overlap table](cross_perturbation_overlap.csv) contains 258 within-model comparisons across intervention families. It records joint errors, marginal error rates, independence expectations within true-label strata, and excess overlap with judgment-cluster intervals. State Swap entries measure reversal sensitivity on the manuscript's common 800-target substitution cohort; they do not assign the original case's correctness label to a substituted jurisdiction.

## Analysis contract

- **Scoring:** threshold the valid-score mean for systematic perturbations, matching the manuscript. Scores below 40 indicate no violation, above 60 violation, and 40-60 abstention. Stored full-record/summary category-plurality labels are checked separately against individual ratings.
- **Case matching:** unique `(item_id, article_full)` targets. Persuasion retains the manuscript's provision-consistent, complete trajectories. Sixteen existing cohort hashes and final correctness counts are reproduced; role comparisons use twelve cohorts complete in all five roles. [pair_coverage.csv](pair_coverage.csv) separates valid comparisons from missing outputs and reconciles them with the manuscript's totals.
- **Failure timing:** first-error incidence uses initially correct cases. The hazard denominator contains cases without an earlier wrong verdict, including those currently abstaining. Recovery and lost-correction rates state their event-conditioned denominators.
- **Uncertainty:** 2,000 percentile bootstrap draws over judgments, seed 731; all targets from a judgment remain together. Conditional denominators are recomputed within each draw. Empty strata have blank estimates. Intervals describe the empirical distribution of the saved outputs.
- **Overlap:** intersect valid targets and require the relevant reference judgments to be correct for error comparisons. State Swap uses decisive original predictions and actual respondent/text substitutions. The label-adjusted expectation is the sum of within-label independence expectations.
- **Scope:** six primary models and their released protocols. The separate old-model nationality experiment is outside these five analyses.

## Placement in the manuscript

Prioritize the endpoint reversals and the first-turn onset with limited recovery in the main Results. Error direction, the full role matrix and cross-perturbation overlap provide appendix detail. Each displayed result should convey one of these findings.

## Reproduction and audit

```sh
python analysis/analyze_fine_grained_failures.py
python analysis/build_fine_grained_report.py
```

[manifest.json](manifest.json) records source hashes, the scoring contract and output checksums. [VALIDATION.json](VALIDATION.json) independently recounts timing from previously published categorical paths, verifies endpoint analysis against published case traces, checks paired role contrasts, and reproduces the manuscript's summary and paraphrase transition counts. [cohorts.csv](cohorts.csv) records membership hashes and denominators.
