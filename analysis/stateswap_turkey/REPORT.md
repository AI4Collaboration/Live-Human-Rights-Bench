# Türkiye Country Swap follow-up

Source release: `b35f6ca1b97017175fab7d9862d29a057529ec2f`. All analysis is offline; no new model calls.

## Main finding

Russia and Ukraine substitutions raise mean violation likelihood for GPT-4o mini and GPT-4.1 mini, but lower it for GPT-5.6-sol. All six directions remain after correction across the nine model-by-destination shifts. GPT-5.6-sol also has a negative Türkiye shift. These are model-specific responses to the same country edits, not estimates of a training-cutoff effect.

## Inputs and scoring

The three models use the same frozen v1.0 inputs (1,000 targets from 947 judgments) and the same summaries, prompts and scoring settings. Every target has an original arm and Türkiye, Russia and Ukraine arms, each with ten requested ratings at temperature 1.0. All 120,000 final ratings parse. The 44 additional parse attempts are retained and checked. Stored means, labels, response histories and text-change flags were verified against the saved responses and deterministic replacement code.

The common comparison includes 785 targets from 742 judgments whose respondent differs from all three destinations, whose summary changes under every substitution, and whose means are valid in all twelve model-arm combinations. Destination-specific substitution counts are 983 for Türkiye, 966 for Russia and 832 for Ukraine. Original Türkiye cases account for the 15-target difference from the original US experiment's 800-target comparison; these are cohort exclusions, not missing model responses.

## Common-cohort results

Likelihood shifts are percentage points relative to the original arm of this follow-up run. Judgment changes and strict reversals use all 785 targets; changes involving abstention are counted separately.

| Model | Destination | Likelihood shift [95% CI] | Judgment change (%) | Strict reversal (%) |
| --- | --- | ---: | ---: | ---: |
| gpt-4o-mini | Türkiye | +0.14 [-0.12, +0.42] | 4.33 | 0.25 |
| gpt-4o-mini | Russia | +0.68 [+0.41, +0.96] | 4.46 | 0.38 |
| gpt-4o-mini | Ukraine | +0.73 [+0.46, +1.00] | 4.71 | 0.25 |
| gpt-4.1-mini | Türkiye | +0.57 [+0.08, +1.05] | 8.28 | 0.76 |
| gpt-4.1-mini | Russia | +1.42 [+0.86, +1.98] | 9.43 | 1.40 |
| gpt-4.1-mini | Ukraine | +1.53 [+0.96, +2.11] | 9.55 | 0.89 |
| gpt-5.6-sol | Türkiye | -1.08 [-1.80, -0.32] | 7.26 | 1.02 |
| gpt-5.6-sol | Russia | -1.05 [-1.73, -0.40] | 7.52 | 1.40 |
| gpt-5.6-sol | Ukraine | -1.38 [-2.10, -0.67] | 8.03 | 1.27 |

## Interpretation and reproducibility

The follow-up tests an additional destination without the US arm. It does not implement the separately planned UK/France comparison with an explicitly fixed Convention framework. Country effects are evaluated as likelihood shifts and judgment transitions, not as accuracy under a transplanted reference verdict. The original six-model US run remains a separate comparison with its own original arms and cohort.

Pointwise intervals use 2,000 judgment-cluster bootstrap draws with seed 731. Family-adjusted bounds use 20,000 draws and Bonferroni quantiles across nine likelihood shifts or six model contrasts. Each draw keeps all targets of a sampled judgment together and retains target weighting. `source_data.csv` includes the common cohort, destination-specific substitutions, all valid pairs and no-substitution diagnostics. The latter are separately sampled inputs, not paired random-seed controls.

Run `python analysis/stateswap_turkey/analyze.py` to reproduce the audit and tables from the pinned Git objects.
