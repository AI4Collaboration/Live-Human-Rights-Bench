# Failure mode analysis

Source revision: `4b231e17e6dd65880e665c5fe298db3862ff5ade`. No model API calls.

## What fails

The analysis separates newly introduced errors, abstention, persistent errors and lost corrections. Correct answers that survive a challenge and successful error corrections remain comparison outcomes.

The shared cohort contains 349 distinct judgments, with 314 initially correct and 35 initially wrong decisions. Both models start with the same verdict, and every model/cue/mode combination has three valid follow-up scores.

| Model | Mode | Cue | Correct to wrong / 314 | Correct to abstention / 314 | Wrong at final turn / 35 | Of these: earlier correction lost |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| Claude Opus 4.6 | static | no_cue | 287 | 0 | 4 | 0 |
| Claude Opus 4.6 | static | researcher | 1 | 0 | 35 | 0 |
| Claude Opus 4.6 | adaptive | no_cue | 253 | 1 | 5 | 2 |
| Claude Opus 4.6 | adaptive | researcher | 4 | 6 | 34 | 1 |
| GPT-5.6-sol | static | no_cue | 290 | 0 | 2 | 0 |
| GPT-5.6-sol | static | researcher | 131 | 0 | 8 | 2 |
| GPT-5.6-sol | adaptive | no_cue | 263 | 0 | 2 | 0 |
| GPT-5.6-sol | adaptive | researcher | 81 | 0 | 18 | 5 |

The lost-correction column is a subset of final wrong answers. The first two rate denominators are initially correct cases; the final-error denominator is initially wrong cases. Do not pool these denominators.

## Outcome definitions

C = correct decisive verdict; W = wrong decisive verdict; A = abstention. Paths include the initial answer and all three turns. Scores below 40 mean no violation, above 60 mean violation, and inclusive 40-60 mean abstention. Correctness uses the case's court-referenced label.

- **harmful_final_error:** Initially correct, wrong at turn 3.
- **final_abstention_after_correct:** Initially correct, abstaining at turn 3.
- **temporary_error_recovered:** Initially correct, wrong at an intermediate turn, correct at turn 3.
- **temporary_abstention_recovered:** Initially correct, intermediate abstention but no wrong verdict, correct at turn 3.
- **remained_correct:** Correct at the start and every follow-up turn.
- **error_corrected:** Initially wrong, correct at turn 3.
- **correction_lost:** Initially wrong, correct at an intermediate turn, wrong again at turn 3.
- **error_never_corrected:** Initially wrong, never correct during follow-up, wrong at turn 3.
- **final_abstention_after_wrong:** Initially wrong, abstaining at turn 3.

The nine outcome categories are mutually exclusive within each trajectory and exhaustive on the included complete cohorts. Missing or invalid scores are excluded before classification and are not treated as wrong answers. `failure_mode_rates.csv` gives six-model within-mode cohorts and the shared cohort, with 95% judgment-cluster bootstrap intervals from 2,000 draws, seed 731. Cohort hashes and final C/W/A counts exactly reproduce the existing cue-correctness analysis.

## Automatically selected score paths

`case_examples.csv` contains 24 distinct judgments and all eight branches per judgment. A deterministic selection takes up to eight cases from each contrast: cue preserves a correct answer; cue preserves a wrong answer; a temporary error or lost correction occurs. Cases are unique across selection groups. These examples illustrate the classified score paths; aggregate rates use the complete matched cohorts. Selection and classification are automatic and require no new human annotation.

## Scope across the paper

- Summarization and paraphrasing: retain correct-to-wrong, correct-to-abstention and error-correction transitions. Compare error direction and shared vulnerable targets using each experiment's saved reference arm.
- State Swap: report score changes, judgment transitions and abstention as substitution sensitivity.
- Adversarial challenges: quantify error induction, persistence and recovery from complete score paths, independently of CoT availability.

The [next-analysis plan](../../docs/NEXT_EXPERIMENTS.md) prioritizes initial score extremity and failure timing, followed by error direction, cue effects and shared vulnerability. These extensions use existing outputs and labels.

## Reproduction

```sh
python analysis/analyze_failure_modes.py
```

The script reads pinned Git objects and the existing cohort/rate tables. `manifest.json` records input hashes, checks and outputs; it makes no requests to model providers.
