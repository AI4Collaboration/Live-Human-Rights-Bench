# Next experiments

## Priority summary

The November rebuttal plan replaces the earlier full-cohort queue. It uses a
frozen 50-judgment sample to answer the actual reviews. No additional full-cohort
runs are scheduled.

| Priority | Work | Status / owner |
| --- | --- | --- |
| Current rebuttal | Repeated no-cue/researcher conversations; opinion-only and neutral reassessment controls; explicit evaluation framing | [Frozen protocol](rebuttal/EXPERIMENTS.md); results and completion are tracked in the [rebuttal index](rebuttal/README.md) |
| Separate assignment | Collect, validate and evaluate post-v1.0 judgments | [New-batch handoff](rebuttal/DELEGATED_TASKS.md#priority-1-evaluate-a-genuinely-new-release) |
| No API | Recover saved claim-level summary coverage and historical adaptive messages | Publish originals if available; do not regenerate historical evidence |

The focused run plans at most 3,900 target replies with a $50 local ceiling.
It reuses saved initial replies and makes no adaptive-challenger calls.
The former 25,398-reply control grid and 84,660-reply repetition proposal are
superseded, not additional pending work.

## No-API additions

The independent paraphrase checks and repaired texts are already released.
The new [input-only sensitivity analysis](../analysis/rebuttal_20261107/existing/paraphrase_sensitivity.csv)
uses the 540 instances retaining all sampled facts in every rewrite.
The [reasoning-availability analysis](../analysis/rebuttal_20261107/existing/reasoning_availability.csv)
compares outcomes with and without recorded explanations.
Both are completed using existing records.

## Evaluation framing and repetitions

[Exact prompts, repetitions, sample selection and cost controls](rebuttal/EXPERIMENTS.md)
are frozen separately from the main experiments. No cue and AI safety researcher
receive contemporaneous repeated references for Opus-4.6 and 5.6-Sol.
V4-Flash supplies the lower-cost comparison for the mechanism controls.
The framing comparison keeps AI researcher identity fixed and changes one
six-word sentence. It tests wording effects rather than proving latent awareness.

## Future work

New defenses, adaptive repetitions, additional roles and lower-temperature
sweeps are outside this rebuttal. A standalone unframed AI researcher arm is
not scheduled. None should be represented as an outstanding required experiment.

### Country Swap

A separate extension could construct substitutions with Convention applicability
and local factual context jointly preserved. The current paper reports screened
judgment shifts rather than scoring substituted cases against original labels.

## Submission material

Internal planning documents are excluded when building an anonymous supplementary
archive. Completed methods, analysis code and de-identified evidence belong in
the research artifact. Credentials, account balances and review administration
do not belong in either artifact.
