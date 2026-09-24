# Country Swap context audit

## Finding

Country substitution is not always a coherent counterfactual. The runner used for the published experiments replaced every respondent-country alias and demonym. It retained named locations, institutions, domestic law and cross-border relationships without a context check.

The audit reconstructs the exact selected summaries and transformations for all 1,000 targets from 947 judgments. Inputs are identical across the original US run and both follow-ups. There are no Nigerian respondents, but five selected summaries mention Nigeria or Nigerian nationality as part of another respondent's case.

## Verified examples

### CASE OF A.R.E. v. GREECE (001-240242)

- Destination: Turkey. Included in the published 768-target follow-up cohort.
- Original: concerns the alleged “pushback” of a Turkish national from Greece to Türkiye in May 2019
- Substituted: concerns the alleged “pushback” of a Turkish national from Türkiye to Türkiye in May 2019
- Interpretation: Origin and destination of a cross-border pushback become the same country.
- [HUDOC source](https://hudoc.echr.coe.int/eng?i=001-240242). Exact input and transformed-text hashes are in `examples.json`.

### CASE OF LEVINTA v. MOLDOVA (No. 2) (001-108607)

- Destination: Russia. Included in the published 768-target follow-up cohort.
- Original: were arrested in Russia in October 2000 and extradited to Moldova
- Substituted: were arrested in Russia in October 2000 and extradited to Russia
- Interpretation: Extradition from Russia to Moldova becomes extradition from Russia to Russia.
- [HUDOC source](https://hudoc.echr.coe.int/eng?i=001-108607). Exact input and transformed-text hashes are in `examples.json`.

### CASE OF TOLESKI v. "THE FORMER YUGOSLAV REPUBLIC OF MACEDONIA" (001-174413)

- Destination: UK. Included in the published 768-target follow-up cohort.
- Original: It found the land was part of the Ohrid lakeshore and of general/public interest under the Protection of Lakes Act and Waters Act, making enforcement legally impossible.
- Substituted: It found the land was part of the Ohrid lakeshore and of general/public interest under the Protection of Lakes Act and Waters Act, making enforcement legally impossible.
- Interpretation: Ohrid lakeshore and the local statutory setting remain after the respondent is changed to the UK.
- [HUDOC source](https://hudoc.echr.coe.int/eng?i=001-174413). Exact input and transformed-text hashes are in `examples.json`.

## Offline sensitivity analysis

The screen was specified from the review concern and input inspection before examining subset scores. It flags environment-related terms, cross-border events, territorial conflicts and a destination already mentioned in the original summary. The same retained targets are used for every model and destination within each comparison family.

These are review flags, not confirmed-invalid labels. A lake or an asylum claim does not by itself make a substitution impossible. Conversely, unflagged texts can still retain incompatible locations or institutions. The restricted comparison measures sensitivity to removing these identifiable contexts; it does not establish a clean country-identity effect.

| Comparison | Full targets | Flagged targets | Remaining targets | Remaining judgments |
| --- | ---: | ---: | ---: | ---: |
| us | 800 | 194 | 606 | 577 |
| followups | 768 | 194 | 574 | 545 |

All 18 follow-up point estimates retain their original directions on the 574 remaining targets. UK substitution still lowers scores for all three models with intervals below zero after correction across 18 comparisons. Russia and Ukraine still raise both mini models' scores. GPT-5.6-sol retains negative Ukraine estimates, although their adjusted intervals include zero. The original US experiment also retains negative estimates in all six models on 606 remaining targets. This screen therefore preserves the main directional pattern while leaving the interpretation as contextual sensitivity.

| Run | Model | Destination | Full shift | Remaining shift [95% CI] |
| --- | --- | --- | ---: | ---: |
| us | claude-opus-4.6 | US | -0.59 | -0.82 [-1.34, -0.30] |
| us | claude-opus-4.6 | Russia | +1.01 | +0.40 [-0.17, +1.03] |
| us | claude-opus-4.6 | Ukraine | +0.70 | +0.20 [-0.40, +0.82] |
| us | gpt-5.6-sol | US | -6.50 | -7.34 [-9.07, -5.72] |
| us | gpt-5.6-sol | Russia | -0.37 | -0.65 [-1.44, +0.14] |
| us | gpt-5.6-sol | Ukraine | -0.84 | -1.10 [-1.94, -0.29] |
| us | deepseek-v4-pro | US | -7.86 | -8.65 [-10.48, -6.99] |
| us | deepseek-v4-pro | Russia | +0.32 | +0.12 [-1.02, +1.29] |
| us | deepseek-v4-pro | Ukraine | +0.04 | -0.44 [-1.55, +0.56] |
| us | deepseek-v4-flash | US | -8.83 | -9.33 [-10.91, -7.90] |
| us | deepseek-v4-flash | Russia | +0.10 | -0.44 [-1.28, +0.53] |
| us | deepseek-v4-flash | Ukraine | -0.22 | -0.50 [-1.34, +0.36] |
| us | qwen3-235b-a22b | US | -2.90 | -2.69 [-3.36, -2.03] |
| us | qwen3-235b-a22b | Russia | +1.20 | +1.51 [+1.04, +2.00] |
| us | qwen3-235b-a22b | Ukraine | +0.79 | +1.06 [+0.58, +1.52] |
| us | qwen3-32b | US | -5.77 | -6.42 [-7.45, -5.39] |
| us | qwen3-32b | Russia | +1.27 | +1.16 [+0.58, +1.77] |
| us | qwen3-32b | Ukraine | +0.84 | +0.74 [+0.24, +1.29] |
| turkey | gpt-4o-mini | Turkey | +0.11 | +0.05 [-0.26, +0.36] |
| turkey | gpt-4o-mini | Russia | +0.66 | +0.53 [+0.24, +0.82] |
| turkey | gpt-4o-mini | Ukraine | +0.70 | +0.71 [+0.41, +1.03] |
| turkey | gpt-4.1-mini | Turkey | +0.36 | +0.18 [-0.32, +0.68] |
| turkey | gpt-4.1-mini | Russia | +1.22 | +1.04 [+0.38, +1.67] |
| turkey | gpt-4.1-mini | Ukraine | +1.33 | +1.25 [+0.62, +1.93] |
| turkey | gpt-5.6-sol | Turkey | -1.09 | -0.98 [-1.86, -0.11] |
| turkey | gpt-5.6-sol | Russia | -1.09 | -0.85 [-1.63, -0.09] |
| turkey | gpt-5.6-sol | Ukraine | -1.40 | -1.30 [-2.19, -0.44] |
| uk | gpt-4o-mini | UK | -1.33 | -1.22 [-1.53, -0.92] |
| uk | gpt-4o-mini | Russia | +0.69 | +0.57 [+0.27, +0.87] |
| uk | gpt-4o-mini | Ukraine | +0.78 | +0.70 [+0.38, +1.01] |
| uk | gpt-4.1-mini | UK | -3.07 | -3.37 [-4.24, -2.55] |
| uk | gpt-4.1-mini | Russia | +1.44 | +1.28 [+0.64, +1.94] |
| uk | gpt-4.1-mini | Ukraine | +1.54 | +1.38 [+0.69, +2.18] |
| uk | gpt-5.6-sol | UK | -2.01 | -2.02 [-2.98, -1.07] |
| uk | gpt-5.6-sol | Russia | -0.60 | -0.36 [-1.15, +0.47] |
| uk | gpt-5.6-sol | Ukraine | -1.13 | -1.22 [-2.11, -0.32] |

Shifts are percentage points relative to the original arm from the same run. Intervals resample judgments and retain the target-weighted mean. `sensitivity.csv` also provides Bonferroni-adjusted intervals across each family's 18 comparisons and categorical-change rates. Original inputs, outputs and published estimates remain intact.

## Pipeline integration

Report these experiments as contextual sensitivity to textual country substitution. Do not treat every transformed case as fact-preserving or give it the original case's reference verdict. The absence of an original-label accuracy calculation already avoids the second error; this audit addresses the distinct input-coherence issue.

The Country Swap runner now applies this screen before model calls. It writes `context_manifest.json` with every target, its eligibility, exclusion reasons and input hashes. Use `--preflight-only` to inspect the manifest without an API key. `--validity-targets uk turkey` reproduces the 574-target shared follow-up cohort. New context-checked runs cannot resume older unscreened checkpoints. Historical inputs and scores remain unchanged.

Reproduce offline with `python analysis/stateswap_context/audit.py`. No model API is imported or called. `input_flags.csv` retains every target and the exact flag terms; `manifest.json` pins all data and score inputs.
