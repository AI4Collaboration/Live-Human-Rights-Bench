# Generator-linked evaluator exclusion

**Takeaway.** The main systematic-perturbation patterns remain after removing generator-linked evaluators. Summary accuracy still decreases for every retained model, with corrections offsetting many losses. Paraphrases still change individual judgments without a common accuracy direction across models or a common response to increasing rewrite strength.

## Fixed comparisons

The diagnostic reaggregates the published inclusive 40-60 abstention rule: scores below 40 indicate no violation, scores above 60 indicate violation, and both endpoints belong to abstention. Summary evaluation compares each target's full-record score with its shared-summary score. Paraphrasing compares each rewrite with the saved original arm from that experiment.

- Summary: exclude DeepSeek V4 Pro and DeepSeek V4 Flash. The summary generator is DeepSeek V4.1 Flash, so this exclusion follows a model-family link rather than an exact-model overlap.
- Paraphrasing: exclude GPT-5.6-sol, the exact model used as both paraphraser and evaluator.

Every retained model keeps all 1,000 paired targets from the same 947 judgments. Counts pool paired model-target observations: 5,000 for all five evaluators, 3,000 for summary after exclusion, and 4,000 per paraphrase strength after exclusion. These are target-weighted counts, not counts of distinct judgments; the 947 judgments are not multiplied into new independent cases. Missing scores retain the source analysis's failure category. Category changes include transitions among no violation, violation, abstention and failure; corrections and losses respectively enter and leave the correct category.

## Paired totals

| Comparison | Evaluators | Paired observations | Category changes | Corrections | Losses | Net correct change | Accuracy change (pp) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Summary, all five | 5 | 5,000 | 699 (13.98%) | 189 | 278 | -89 | -1.78 |
| Summary, exclusion | 3 | 3,000 | 415 (13.83%) | 110 | 175 | -65 | -2.17 |
| Light, all five | 5 | 5,000 | 518 (10.36%) | 166 | 182 | -16 | -0.32 |
| Light, exclusion | 4 | 4,000 | 469 (11.72%) | 146 | 169 | -23 | -0.57 |
| Medium, all five | 5 | 5,000 | 550 (11.00%) | 182 | 198 | -16 | -0.32 |
| Medium, exclusion | 4 | 4,000 | 494 (12.35%) | 159 | 179 | -20 | -0.50 |
| Heavy, all five | 5 | 5,000 | 503 (10.06%) | 176 | 159 | +17 | +0.34 |
| Heavy, exclusion | 4 | 4,000 | 456 (11.40%) | 158 | 144 | +14 | +0.35 |

## What remains after exclusion

**Summary losses remain small in aggregate but hide larger opposing changes.** Accuracy changes range from -2.4 to -2.0 percentage points across the three retained models; category-change rates range from 10.7 to 16.1%. The pooled net change is -65 correct answers (-2.17 points), combining 110 corrections with 175 losses. Correct-to-abstention transitions (109) exceed abstention-to-correct transitions (57) by 52, accounting for 80.0% of the net loss. The all-five pooled change was -1.78 points.

**Paraphrase effects remain model dependent.** The five retained evaluators still have both positive and negative net accuracy changes at each rewrite strength:

| Rewrite | Per-model accuracy change (pp) | Per-model category changes (%) |
| --- | ---: | ---: |
| Light | -1.4 to +0.5 | 7.6 to 16.1 |
| Medium | -1.3 to +0.2 | 8.4 to 16.9 |
| Heavy | -0.9 to +1.9 | 7.5 to 15.6 |

As rewrite strength increases from light to medium to heavy, 2 retained models have nondecreasing accuracy changes, 2 have nonmonotonic changes, and 0 have nonincreasing changes. Pooled accuracy changes are -0.57, -0.50 and +0.35 points, respectively. Removing GPT-5.6-sol leaves the full -1.4 to +1.9 point range across model/strength combinations intact.

## Interpretation and reproduction

The diagnostic establishes that these aggregate patterns do not depend on including the specified generator-linked evaluators. It retains the original generated texts and does not test a replacement generator or establish generator independence. Its useful addition is this direct evaluator-dependence check; the underlying model results and headline conclusions are unchanged.

Run `python analysis/generator_exclusion/analyze.py` from the repository root. The standard-library script reads committed tables and generator-role records from revision `d8a3a07e93f983fdf92b0557a5c028deaba43162`, validates source hashes and all four published five-model totals, and writes the three CSVs, this report and the manifest. The tables trace to raw-score revision `24bb24f23ed478bb1a5fb0e22cbc8cb5ea4284c3` through the threshold analysis manifest. No API calls, new labels, bootstrap, confidence intervals or figures are added.

- `pooled.csv`: all-five and excluded-evaluator paired totals, ranges, transition decomposition, model lists and cohort hash.
- `per_model.csv`: all 24 published model/contrast estimates with explicit retention flags.
- `paraphrase_strength.csv`: five three-strength sequences with retention flags and direction classification.
- `manifest.json`: source byte hashes, output hashes, generator/evaluator mapping and passed checks.
