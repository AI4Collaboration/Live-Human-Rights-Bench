# Both Country Swap follow-ups

The figure retains all 18 model-by-destination estimates from both follow-ups. The repeated Russia and Ukraine conditions are displayed separately. Each difference uses the original arm collected in the same run.

The common cohort contains 768 targets from 725 judgments with an actual substitution in all four destination countries.

| Run | Model | Destination | Shift [95% CI] | Judgment change (%) | Strict reversal (%) |
| --- | --- | --- | ---: | ---: | ---: |
| turkey | gpt-4o-mini | Turkey | +0.11 [-0.16, +0.38] | 4.17 | 0.26 |
| turkey | gpt-4o-mini | Russia | +0.66 [+0.41, +0.94] | 4.30 | 0.39 |
| turkey | gpt-4o-mini | Ukraine | +0.70 [+0.44, +0.98] | 4.56 | 0.26 |
| turkey | gpt-4.1-mini | Turkey | +0.36 [-0.09, +0.79] | 7.81 | 0.52 |
| turkey | gpt-4.1-mini | Russia | +1.22 [+0.69, +1.75] | 8.98 | 1.17 |
| turkey | gpt-4.1-mini | Ukraine | +1.33 [+0.80, +1.91] | 8.98 | 0.65 |
| turkey | gpt-5.6-sol | Turkey | -1.09 [-1.89, -0.41] | 7.42 | 1.04 |
| turkey | gpt-5.6-sol | Russia | -1.09 [-1.84, -0.43] | 7.68 | 1.43 |
| turkey | gpt-5.6-sol | Ukraine | -1.40 [-2.20, -0.70] | 8.20 | 1.30 |
| uk | gpt-4o-mini | UK | -1.33 [-1.60, -1.07] | 4.43 | 0.00 |
| uk | gpt-4o-mini | Russia | +0.69 [+0.41, +0.99] | 4.95 | 0.13 |
| uk | gpt-4o-mini | Ukraine | +0.78 [+0.51, +1.06] | 4.82 | 0.13 |
| uk | gpt-4.1-mini | UK | -3.07 [-3.78, -2.40] | 11.85 | 1.82 |
| uk | gpt-4.1-mini | Russia | +1.44 [+0.93, +1.98] | 8.46 | 0.91 |
| uk | gpt-4.1-mini | Ukraine | +1.54 [+0.96, +2.16] | 8.59 | 1.04 |
| uk | gpt-5.6-sol | UK | -2.01 [-2.88, -1.16] | 8.98 | 2.47 |
| uk | gpt-5.6-sol | Russia | -0.60 [-1.31, +0.10] | 7.03 | 1.17 |
| uk | gpt-5.6-sol | Ukraine | -1.13 [-1.87, -0.39] | 6.64 | 1.69 |

The original US experiment retains its own cohort and source tables. No records or previously reported runs are deleted. Destination-specific analysis and the original follow-up cohorts remain in their respective source directories.

Reproduce with `python analysis/stateswap_followups/analyze.py` after generating both follow-up audits.
