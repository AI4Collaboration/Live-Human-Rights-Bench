# Within-target score variability

**Summary score variance rises in two models and falls in four.** Only DeepSeek V4 Flash has an increase whose paired 95% interval excludes zero; DeepSeek V4 Pro and both Qwen models have decreases whose intervals exclude zero.

We calculate the sample standard deviation and variance of the ten saved scores separately for each target and input. We then average over the same complete target pairs in both arms. This measures variation across repeated responses to one input, rather than variation across different cases.

| Model | Targets | Full-record mean variance | Summary mean variance | Paired variance difference [95% CI] |
| --- | ---: | ---: | ---: | ---: |
| Claude Opus 4.6 | 1000 | 3.00 | 2.15 | -0.85 [-1.93, +0.16] |
| GPT-5.6-sol | 1000 | 146.04 | 176.79 | +30.75 [-2.57, +63.89] |
| DeepSeek V4 Pro | 999 | 461.54 | 382.83 | -78.71 [-120.24, -37.65] |
| DeepSeek V4 Flash | 1000 | 217.80 | 248.03 | +30.24 [+3.50, +56.91] |
| Qwen3-235B | 999 | 168.78 | 108.17 | -60.61 [-75.21, -46.16] |
| Qwen3-32B | 997 | 358.03 | 188.84 | -169.19 [-197.85, -140.97] |

Variance uses squared score points. For comparison, the following table reports the mean within-target SD in score points. Averaging variances gives more weight to targets with large dispersion than averaging SDs.

| Model | Targets | Full-record mean SD | Summary mean SD | Paired SD difference [95% CI] |
| --- | ---: | ---: | ---: | ---: |
| Claude Opus 4.6 | 1000 | 0.76 | 0.57 | -0.19 [-0.31, -0.07] |
| GPT-5.6-sol | 1000 | 4.65 | 6.33 | +1.67 [+0.89, +2.48] |
| DeepSeek V4 Pro | 999 | 14.62 | 13.30 | -1.31 [-2.20, -0.42] |
| DeepSeek V4 Flash | 1000 | 12.30 | 12.16 | -0.13 [-0.76, +0.49] |
| Qwen3-235B | 999 | 10.73 | 8.29 | -2.44 [-2.90, -1.98] |
| Qwen3-32B | 997 | 14.83 | 10.19 | -4.64 [-5.31, -3.96] |

Scores use the 0-100 scale. Differences are summary minus full record. Intervals use 2,000 paired judgment-cluster bootstrap resamples, seed 731; targets from the same judgment stay together. Five pairs with one missing summary score are excluded, leaving 5,995 model-target pairs. Existing published mean-SD estimates are reproduced to numerical precision.

The [source table](source_data.csv) includes variance estimates and paired intervals as well as standard deviations. The [input manifest](manifest.json) records immutable Git input hashes. No model API calls are made.

The separate [five-score analysis](../reliability_controls/REPORT.md) compares categorical judgments at a common sample size and shows input changes beyond same-input sampling variation.

Reproduce from the repository root: `python analysis/analyze_summary_variability.py`.
