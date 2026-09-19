# Additional analyses of judgment reliability

Source GitHub revision: `4b231e17e6dd65880e665c5fe298db3862ff5ade`. All results below use existing outputs; no model calls.

## Main findings

- **The researcher cue preserves both correct and incorrect starting judgments.** On the shared 349 cases, Claude's static retention of correct answers rises from 27/314 to 313/314, while correction of initial errors falls from 31/35 to 0/35. GPT retains 183/314 correct answers and corrects 27/35 errors with the cue. The adaptive comparison shows the same direction.
- **Cue sensitivity is concentrated in Claude and GPT.** Gains in correct-answer retention across the model-specific matched cohorts are Claude: 78.9-90.8 percentage points; GPT: 45.3-50.6 percentage points; DeepSeek: 4.7-9.2 percentage points; Qwen: 0.0-2.5 percentage points.
- **Summary-induced judgment changes exceed same-input sampling variability in all six models.** With five ratings on each side, the excess over the full-record sampling reference is 3.2-15.5 percentage points. All six paired 95% intervals lie above zero. This supports input sensitivity beyond the observed variability of repeated scoring.

## 1. Researcher cue: retaining correct answers versus correcting errors

Every contrast matches complete no-cue and AI safety researcher trajectories within the same model and mode, starting from the identical initial response. The released follow-up provision filter matches the manuscript. Accuracy counts abstention as incorrect. Rates below are final-turn percentages.

| Model | Mode | Initially correct n | Correct retained: no cue / researcher | Initially wrong n | Errors corrected: no cue / researcher | Correction difference, pp [95% CI] |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Claude Opus 4.6 | static | 684 | 8.2 / 99.0 | 190 | 96.3 / 1.6 | -94.7 [-97.8, -91.4] |
| Claude Opus 4.6 | adaptive | 398 | 17.8 / 96.7 | 82 | 87.8 / 1.2 | -86.6 [-93.3, -78.9] |
| GPT-5.6-sol | static | 780 | 8.5 / 53.7 | 143 | 98.6 / 76.9 | -21.7 [-29.1, -15.3] |
| GPT-5.6-sol | adaptive | 634 | 20.3 / 71.0 | 96 | 96.9 / 54.2 | -42.7 [-52.5, -32.9] |
| DeepSeek V4 Pro | static | 467 | 0.6 / 6.9 | 136 | 100.0 / 93.4 | -6.6 [-11.1, -2.8] |
| DeepSeek V4 Pro | adaptive | 292 | 0.0 / 9.2 | 91 | 96.7 / 91.2 | -5.5 [-12.6, +1.2] |
| DeepSeek V4 Flash | static | 634 | 1.1 / 5.8 | 215 | 97.7 / 92.1 | -5.6 [-9.3, -2.2] |
| DeepSeek V4 Flash | adaptive | 435 | 11.0 / 17.0 | 161 | 87.0 / 82.6 | -4.3 [-12.0, +3.2] |
| Qwen3-235B | static | 622 | 0.8 / 0.8 | 208 | 97.6 / 97.6 | +0.0 [-1.9, +1.9] |
| Qwen3-235B | adaptive | 405 | 10.6 / 13.1 | 147 | 81.0 / 78.9 | -2.0 [-9.3, +5.6] |
| Qwen3-32B | static | 633 | 0.3 / 0.3 | 230 | 99.1 / 99.1 | +0.0 [-1.8, +1.7] |
| Qwen3-32B | adaptive | 425 | 3.1 / 3.8 | 164 | 89.6 / 86.6 | -3.0 [-8.8, +2.3] |

### Strict shared 349-case cohort

Both models start with the same verdict on these cases: 314 initially correct and 35 initially wrong. The same cases have all eight cue/model/mode branches complete.

| Model | Mode | Correct retained: no cue / researcher | Errors corrected: no cue / researcher |
| --- | --- | ---: | ---: |
| Claude Opus 4.6 | static | 27/314 to 313/314 | 31/35 to 0/35 |
| Claude Opus 4.6 | adaptive | 60/314 to 304/314 | 30/35 to 0/35 |
| GPT-5.6-sol | static | 24/314 to 183/314 | 33/35 to 27/35 |
| GPT-5.6-sol | adaptive | 51/314 to 233/314 | 33/35 to 17/35 |

Reduced reversal can preserve both correct and incorrect starting judgments. This comparison measures persistence under opposing claims; the experiment holds the case evidence fixed.

**Data:** [rates](cue_correctness_rates.csv), [paired contrasts and intervals](cue_correctness_contrasts.csv), [cohorts](cue_cohorts.csv).

## 2. Equal-size sampling comparison

A judgment change means a transition between violation, no violation or abstention. For each target and input, enumerate all 252 choices of five out of ten saved ratings. Compare each full-record subset with its disjoint complement (reference/reference), and do the same for summary/summary. For reference/summary, average over all 252 x 252 independent subset pairs, computed exactly from category probabilities. Every compared prediction thresholds a mean of five scores.

The reference-only excess is reference/summary minus reference/reference. A symmetric comparison subtracts the average of the two within-input rates. The reference-only contrast includes changes in summary variability; the symmetric contrast accounts for variability in both representations.

| Model | Targets | Reference/reference change % | Summary/summary change % | Reference/summary change % | Excess over reference, pp [95% CI] | Excess over symmetric reference, pp [95% CI] |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Claude Opus 4.6 | 1000 | 0.59 | 0.68 | 16.06 | +15.47 [+13.19, +17.91] | +15.43 [+13.17, +17.81] |
| GPT-5.6-sol | 1000 | 3.85 | 5.87 | 10.78 | +6.93 [+5.42, +8.48] | +5.92 [+4.70, +7.19] |
| DeepSeek V4 Pro | 999 | 12.87 | 12.01 | 17.21 | +4.35 [+2.98, +5.78] | +4.78 [+3.73, +5.88] |
| DeepSeek V4 Flash | 1000 | 7.45 | 8.63 | 14.12 | +6.67 [+5.11, +8.37] | +6.08 [+4.73, +7.50] |
| Qwen3-235B | 999 | 12.52 | 10.02 | 18.02 | +5.51 [+3.86, +7.11] | +6.75 [+5.35, +8.15] |
| Qwen3-32B | 997 | 12.14 | 9.15 | 15.33 | +3.19 [+1.88, +4.55] | +4.69 [+3.61, +5.80] |

The cohort requires ten valid ratings in both arms: 5,995 model-target pairs, excluding five rows with one missing summary rating each. The manuscript's ten-score mean analysis retains all 6,000 pairs using available scores. Five-score and ten-score changes are distinct estimands; the sampling comparison does not replace the published ten-score results.

**Data:** [all metrics and paired intervals](sampling_variation.csv), [five excluded rows](sampling_exclusions.csv). The CSV also includes strict reversals, absolute score differences and rating standard deviations.

## 3. Inference and reproduction

Intervals are percentile intervals from 2,000 judgment-cluster bootstrap resamples, seed 731. All target rows from a judgment stay together. Conditional cue-rate denominators are recomputed in each draw. Paired conditions share each bootstrap draw. Exact subset averaging contributes no Monte Carlo error. The intervals describe variation across judgments, conditional on the saved ratings and conversations.

```sh
python analysis/analyze_reliability_controls.py
python -m unittest discover -s tests -p test_reliability_controls.py
```

The script reads committed Git objects and works with a sparse checkout. Input hashes, cohort checks, method settings and output hashes are in [manifest.json](manifest.json). No experiment runner or API client is imported.
