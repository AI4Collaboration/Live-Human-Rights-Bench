# UK State Swap analysis

Source revision: `05b96bf53698e503f18f25bd44c3a66f47b67d20`. All analysis is offline; no new model calls.

## Finding

Replacing the respondent with the United Kingdom lowers mean violation likelihood in all three GPT models. Each UK effect remains negative after correction across nine model-by-destination effects. Russia and Ukraine raise scores for both mini models. GPT-5.6-sol has a negative Ukraine effect; its Russia estimate has a pointwise interval crossing zero.

## Comparison

All nine comparisons use the same 783 targets from 740 judgments. Every retained target has a different original respondent and changed summary text in all three destination arms. Each model is compared with the original arm collected in this UK run. Effects are score changes on a 0-100 scale, expressed in percentage points.

| Model | Destination | Likelihood shift [95% CI] | Judgment change (%) | Strict reversal (%) |
| --- | --- | ---: | ---: | ---: |
| gpt-4o-mini | UK | -1.32 [-1.59, -1.05] | 4.47 | 0.00 |
| gpt-4o-mini | Russia | +0.68 [+0.39, +0.97] | 4.98 | 0.13 |
| gpt-4o-mini | Ukraine | +0.78 [+0.51, +1.07] | 4.85 | 0.13 |
| gpt-4.1-mini | UK | -3.06 [-3.74, -2.39] | 11.75 | 1.79 |
| gpt-4.1-mini | Russia | +1.39 [+0.86, +1.90] | 8.43 | 0.89 |
| gpt-4.1-mini | Ukraine | +1.52 [+0.95, +2.14] | 8.43 | 1.02 |
| gpt-5.6-sol | UK | -2.01 [-2.85, -1.19] | 9.07 | 2.43 |
| gpt-5.6-sol | Russia | -0.59 [-1.29, +0.09] | 7.02 | 1.15 |
| gpt-5.6-sol | Ukraine | -1.11 [-1.85, -0.35] | 6.64 | 1.66 |

The UK condition changes 4.5%, 11.7% and 9.1% of categorical judgments for GPT-4o mini, GPT-4.1 mini and GPT-5.6-sol. Most changes enter or leave abstention. The respective strict reversal rates are 0.0%, 1.8% and 2.4%.

## Additional analysis

Restricting the comparison to Convention articles removes Protocol targets and leaves 675 targets from 641 judgments. The UK effects remain negative after correction across nine effects: -1.22 for GPT-4o mini, -2.94 for GPT-4.1 mini and -1.84 for GPT-5.6-sol. This subset is reported in `convention_articles_sensitivity.csv`.

`destination_contrasts.csv` compares UK directly with Russia and Ukraine on the same targets. Five of the six differences remain below zero after correction; the adjusted interval for Sol's UK-minus-Ukraine contrast crosses zero. `model_contrasts.csv` tests differences between Sol and the earlier models directly.

## Validation and reproducibility

All 12,000 records and 120,000 final ratings were checked against the canonical targets and saved raw responses. The audit reproduces means and predictions and checks all response histories. There are 57 retained parse retries. Configurations match the v1.0 input hashes and the released prompt and country-replacement code.

The UK destination changes the respondent and summary text for 981 targets. The corresponding counts are 966 for Russia and 832 for Ukraine. Their intersection yields the 783-target common comparison. The other 217 targets are excluded by this comparison definition rather than by missing scores.

Pointwise intervals use 2,000 judgment-cluster bootstrap draws with seed 731. Family intervals use 20,000 draws and Bonferroni quantiles. Each resample retains all targets from a judgment and preserves the target-weighted estimand. Effects are analyzed within this run; the Türkiye run keeps its own original arms and cohort.

Reproduce with `python analysis/stateswap_uk/analyze.py`.
