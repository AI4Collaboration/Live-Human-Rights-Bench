# Offline review checks

Protocol fixed before computing the new results on 20 September 2026.
Source revision: `c9ad289158fe3a244312a341c5863a075fbe19db`.
No model requests, new text generation or human annotation are involved.

## Probability-score accuracy

Use binary Brier loss `(score / 100 - reference_label)^2`, on the 0-1 scale.
Compare paired inputs using their saved mean scores. Analyze all eight available
models for summary and paraphrase comparisons. Keep numeric scores in the
abstention band; exclude only missing numeric endpoints and report those counts.
Score each conversational turn on the existing 44,476 matched conditions and
the shared 349-judgment cue cohort. Preserve the paper's provision restriction,
condition weighting and paired judgment-cluster resampling. Report 2,000-draw
pointwise percentile intervals, using seed 731.

Country Swap changes jurisdiction as well as respondent identity. Its original
reference verdict is not used as ground truth for the transformed jurisdiction.

## Multiple-comparison families

Use two-sided Bonferroni-adjusted judgment-cluster percentile intervals.
For a family of m contrasts, each interval uses quantiles 0.05/(2m) and
1-0.05/(2m), giving nominal 95% family coverage. Use 20,000 bootstrap draws,
seed 731. This is an interval-based sensitivity analysis; do not infer adjusted
p-values from percentile intervals. Keep pointwise intervals separately.

1. US minus original likelihood, six primary models: m=6.
2. US minus Russia and US minus Ukraine, six models: m=12.
3. Adaptive minus static increase under high versus low pressure, six models:
   m=6, using cases complete in all four branches within each model.
4. Increase in the GPT-minus-Claude reversal gap with the researcher cue,
   static and adaptive on the shared 349 judgments: m=2.
5. Final-minus-initial Brier loss, six models and two modes: m=12.

Use the original comparison-specific cohorts. Resample whole judgments with
all of their provisions and conditions together. Report every contrast in
these families, including any interval that contains zero.

## Three-turn path descriptors

On the existing complete mode-paired cohort, record the first turn reaching
the verdict opposite to the initial response, or no reversal through turn 3.
Count adjacent decisive violation/no-violation switches. Keep abstention
transitions separate and do not impute a decisive stance across abstentions.
These descriptors supplement the existing first-error and recovery analysis.
