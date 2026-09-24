# Offline review analyses

All results reuse stored scores at GitHub revision `c9ad289158fe3a244312a341c5863a075fbe19db`. **No new model calls.**

## Main findings

- Final conversational Brier error increases by **0.1143-0.5442** across all six models and both modes. All twelve increases retain positive Bonferroni-adjusted bootstrap intervals.
- Summary Brier changes span **-0.0059 to +0.0167** across eight models. Paraphrase changes span **-0.0125 to +0.0104**, without a common direction across strengths.
- Five of six US likelihood shifts remain negative after within-family correction. Claude's estimate is -0.5924 likelihood points, with adjusted interval **[-1.2861, +0.0995]**. All twelve US-versus-Russia/Ukraine contrasts remain negative.
- All six pressure-by-mode interactions and both researcher-induced model-gap increases retain positive adjusted intervals. The latter intervals are **[36.39, 50.43]** static and **[15.47, 30.66]** adaptive percentage points.

## Probability-forecast error

Brier error is `(score / 100 - reference)^2`, on a 0-1 scale. Positive changes indicate worse probability forecasts. Numeric scores in the abstention band are included. This is not a calibration-only measure.

| Model | Summary change [95% CI] | Static dialogue change [95% CI] | Adaptive dialogue change [95% CI] |
| --- | --- | --- | --- |
| Claude Opus 4.6 | +0.0048 [-0.0037, +0.0131] | +0.1446 [+0.1250, +0.1636] | +0.1143 [+0.0973, +0.1313] |
| GPT-5.6-sol | -0.0059 [-0.0183, +0.0051] | +0.5164 [+0.4728, +0.5583] | +0.3866 [+0.3495, +0.4233] |
| DeepSeek V4 Pro | +0.0050 [-0.0044, +0.0137] | +0.5442 [+0.4855, +0.6027] | +0.5030 [+0.4490, +0.5589] |
| DeepSeek V4 Flash | +0.0068 [-0.0029, +0.0166] | +0.5094 [+0.4585, +0.5579] | +0.4145 [+0.3712, +0.4557] |
| Qwen3-235B | +0.0080 [+0.0013, +0.0146] | +0.5385 [+0.4896, +0.5870] | +0.4637 [+0.4221, +0.5051] |
| Qwen3-32B | +0.0112 [+0.0038, +0.0189] | +0.4261 [+0.3821, +0.4714] | +0.3788 [+0.3387, +0.4197] |
| GPT-4o mini | +0.0167 [+0.0085, +0.0238] | Not evaluated | Not evaluated |
| GPT-4.1 mini | +0.0152 [+0.0050, +0.0248] | Not evaluated | Not evaluated |

All summary pairs number 1,000. Missing-score exclusions occur in paraphrase: DeepSeek V4 Pro retains 985/981/982 and V4 Flash 1,000/999/999 for light/medium/heavy; all other model-strength pairs retain 1,000. Dialogue weights each of the 44,476 matched conditions equally, as in the main results.

## Cue and turn descriptors

On the shared 349 cases, the static researcher cue lowers final Brier error from 0.789 to 0.097 for Claude and from 0.833 to 0.388 for GPT. Adaptive values change from 0.627 to 0.105 and from 0.733 to 0.268, respectively. These aggregate improvements coexist with preservation of some initial errors.

First reversal is the earliest opposite decisive verdict at turn 1, 2 or 3. No reversal is a separate outcome, not an imputed fourth turn. Adjacent switch counts require direct violation/no-violation transitions; abstention transitions are excluded and any abstention is counted separately. These descriptors do not require initially correct answers.

## Sources and uncertainty

- [Fixed analysis protocol](../review_followup/OFFLINE_PROTOCOL.md): five families, specified before computation.
- [Systematic scores](systematic_brier.csv), [all dialogue turns](dialogue_brier.csv), [cue scores](cue_brier.csv), [paired cue changes](cue_brier_contrasts.csv), [turn descriptors](turn_descriptors.csv).
- [Multiple-comparison intervals](multiplicity.csv): 38 contrasts, 20,000 judgment-cluster draws; Bonferroni-adjusted percentile bounds with nominal 95% coverage within each family. Pointwise Brier intervals use 2,000 draws. All use seed 731.
- [Manifest](manifest.json) binds immutable input bytes and generated tables. [Validation](validation.json) independently recomputes scalar point estimates, checks counts, cohorts, family sizes and hashes.

Country Swap receives no Brier score against the original reference: changing jurisdiction does not supply a new ground-truth outcome. Repeated conditions are retained within judgment clusters; they are not independent cases.

## Reproduce

```text
python analysis/analyze_review_offline.py
python analysis/report_review_offline.py
```
