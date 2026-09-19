# Generator-linked evaluator exclusion

**Takeaway.** The main systematic-perturbation patterns remain after removing generator-linked evaluators. Summary accuracy still decreases for every retained model, with corrections offsetting many losses. Paraphrases still change individual judgments without a common accuracy direction across models or a common response to increasing rewrite strength.

## Fixed comparisons

The diagnostic reaggregates the published inclusive 40-60 abstention rule: scores below 40 indicate no violation, scores above 60 indicate violation, and both endpoints belong to abstention. Summary evaluation compares each target's full-record score with its shared-summary score. Paraphrasing compares each rewrite with the saved original arm from that experiment.

- Summary: exclude DeepSeek V4 Pro and DeepSeek V4 Flash. The summary generator is DeepSeek V4.1 Flash, so this exclusion follows a model-family link rather than an exact-model overlap.
- Paraphrasing: exclude GPT-5.6-sol, the exact model used as both paraphraser and evaluator.

Every retained model keeps all 1,000 paired targets from the same 947 judgments. Counts pool paired model-target observations: 6,000 for all six evaluators, 4,000 for summary after exclusion, and 5,000 per paraphrase strength after exclusion. These are target-weighted counts, not counts of distinct judgments; the 947 judgments are not multiplied into new independent cases. Missing scores retain the source analysis's failure category. Category changes include transitions among no violation, violation, abstention and failure; corrections and losses respectively enter and leave the correct category.

## Paired totals

| Comparison | Evaluators | Paired observations | Category changes | Corrections | Losses | Net correct change | Accuracy change (pp) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Summary, all six | 6 | 6,000 | 859 (14.32%) | 234 | 336 | -102 | -1.70 |
| Summary, exclusion | 4 | 4,000 | 575 (14.38%) | 155 | 233 | -78 | -1.95 |
| Light, all six | 6 | 6,000 | 622 (10.37%) | 192 | 222 | -30 | -0.50 |
| Light, exclusion | 5 | 5,000 | 573 (11.46%) | 172 | 209 | -37 | -0.74 |
| Medium, all six | 6 | 6,000 | 656 (10.93%) | 209 | 232 | -23 | -0.38 |
| Medium, exclusion | 5 | 5,000 | 600 (12.00%) | 186 | 213 | -27 | -0.54 |
| Heavy, all six | 6 | 6,000 | 606 (10.10%) | 209 | 189 | +20 | +0.33 |
| Heavy, exclusion | 5 | 5,000 | 559 (11.18%) | 191 | 174 | +17 | +0.34 |

## What remains after exclusion

**Summary losses remain small in aggregate but hide larger opposing changes.** Accuracy changes range from -2.4 to -1.3 percentage points across the four retained models; category-change rates range from 10.7 to 16.1%. The pooled net change is -78 correct answers (-1.95 points), combining 155 corrections with 233 losses. Correct-to-abstention transitions (160) exceed abstention-to-correct transitions (96) by 64, accounting for 82.1% of the net loss. The all-six pooled change was -1.70 points.

**Paraphrase effects remain model dependent.** The five retained evaluators still have both positive and negative net accuracy changes at each rewrite strength:

| Rewrite | Per-model accuracy change (pp) | Per-model category changes (%) |
| --- | ---: | ---: |
| Light | -1.4 to +0.5 | 7.6 to 16.1 |
| Medium | -1.3 to +0.2 | 8.4 to 16.9 |
| Heavy | -0.9 to +1.9 | 7.5 to 15.6 |

As rewrite strength increases from light to medium to heavy, 3 retained models have nondecreasing accuracy changes, 2 have nonmonotonic changes, and 0 have nonincreasing changes. Pooled accuracy changes are -0.74, -0.54 and +0.34 points, respectively. Removing GPT-5.6-sol leaves the full -1.4 to +1.9 point range across model/strength combinations intact.

## Interpretation and reproduction

The diagnostic establishes that these aggregate patterns do not depend on including the specified generator-linked evaluators. It retains the original generated texts and does not test a replacement generator or establish generator independence. Its useful addition is this direct evaluator-dependence check; the underlying model results and headline conclusions are unchanged.

Run `python analysis/generator_exclusion/analyze.py` from the repository root. The standard-library script reads committed tables and generator-role records from revision `66e9f06451ac3463cb7dd6bc6e995e1fa67f9220`, validates source hashes and all four published six-model totals, and writes the three CSVs, this report and the manifest. The tables trace to raw-score revision `24bb24f23ed478bb1a5fb0e22cbc8cb5ea4284c3` through the threshold analysis manifest. No API calls, new labels, bootstrap, confidence intervals or figures are added.

- `pooled.csv`: all-six and excluded-evaluator paired totals, ranges, transition decomposition, model lists and cohort hash.
- `per_model.csv`: all 24 published model/contrast estimates with explicit retention flags.
- `paraphrase_strength.csv`: six three-strength sequences with retention flags and direction classification.
- `manifest.json`: source byte hashes, output hashes, generator/evaluator mapping and passed checks.
