# Analysis directory

These reports use saved experiment outputs. Each report identifies its source
revision, cohort, metric and reproduction command. Recomputing an analysis does
not launch model experiments.

## Main results

| Question | Report | Scope |
| --- | --- | --- |
| How accurate are the models, and does case date matter? | [Baseline and time windows](model_time_windows/REPORT.md) | Six primary models plus two earlier GPT mini models |
| How do country substitutions affect judgments? | [Context-screened Country Swap](stateswap_context/REPORT.md) | 606 targets for the original comparison; 574 for the combined follow-ups |
| How do input changes compare with sampling variation? | [Reliability controls](reliability_controls/REPORT.md) | Summary changes and cue effects by initial correctness |
| How do cues affect reasoning length and evaluation language? | [Full-explanation CoT analysis](reasoning_traces/full_text/README.md) | Complete recorded explanations; paired availability and three-turn cohorts |
| What do the additional opinion and identity controls show? | [September controls](september_controls/REPORT.md) | Separate published runs with their own initial responses |

## Supporting analyses

| Topic | Report |
| --- | --- |
| Reversal, recovery and error persistence | [Failure modes](failure_modes/REPORT.md) |
| Initial certainty, error direction and shared vulnerabilities | [Fine-grained failures](fine_grained_failures/REPORT.md) |
| Alternative score thresholds | [Threshold sensitivity](threshold_sensitivity/REPORT.md) |
| Brier scores, multiple comparisons and turn descriptors | [Offline review analyses](review_offline/REPORT.md) |
| Within-target summary score variance | [Summary variability](summary_variability/REPORT.md) |
| Excluding generator-linked evaluators | [Evaluator exclusions](generator_exclusion/REPORT.md) |
| Individual destination follow-ups | [Türkiye](stateswap_turkey/REPORT.md), [UK](stateswap_uk/REPORT.md) |
| Combined follow-ups before context screening | [Full-cohort comparison](stateswap_followups/REPORT.md) |
| Whole-cohort reasoning-run scores and supplementary text evidence | [CoT index](reasoning_traces/README.md) |
| A worked case with perturbations and an adversarial opinion | [Case example](case_walkthrough/README.md) |
| Validation of reasoning-to-fact paragraph links | [Human annotation](../docs/ANNOTATION.md) |
| Source and summary review binding | [Offline review protocol](review_followup/OFFLINE_PROTOCOL.md) |

## Reading the results

- Use each report's denominator. The v1.0 target count, valid score cohort,
  initially correct subset and recorded-text cohort are different quantities.
- Use the context-screened Country Swap report for manuscript comparisons.
  The destination reports retain the full source cohorts for audit.
- Use `reasoning_traces/full_text/` for cue comparisons of reasoning content
  and length. `language/` retains the original phrase evidence on all available
  first-turn explanations. Its Opus denominator differs from the paired cohort.
- `reasoning_traces/deep_dive/` contains supplementary score-path analysis and
  selected examples. Those examples do not establish a pattern's prevalence.
- Raw experiments remain in [data/experiments](../data/experiments/). Reports
  read frozen revisions or record source hashes so their inputs can be recovered.

Experiment plans are maintained separately in
[Next experiments](../docs/NEXT_EXPERIMENTS.md). New model runs are on hold.
