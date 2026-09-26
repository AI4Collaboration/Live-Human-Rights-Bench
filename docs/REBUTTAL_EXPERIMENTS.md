# Potential rebuttal experiments

Planning only. Exclude this file and its contents from the supplementary submission.
No experiment is authorized or scheduled here.

## Standalone AI researcher cue

Compare `I am an AI researcher.` with the completed No cue, Lawyer and AI safety
researcher settings. Use the same targets, saved initial replies, pressure,
challenge text, mode and turn; report compatible-cohort counts rather than pooling
separate runs. Distinguish reversals of correct judgments from correction of errors.

Possible models: GPT-5.6-sol, Claude Opus 4.6 and DeepSeek V4 Flash.
Optional full-cohort budget: (978 + 918 + 926) x 3 turns = 8,466 target replies,
excluding retries. This is not included in the active first-batch budget.

The separate neutral-versus-evaluation-framing experiment can retain the same
AI researcher prefix in both arms without running this standalone role condition.

## Other conditional follow-ups

| Reviewer question | Possible response | Scope |
| --- | --- | --- |
| Does the cue effect persist across repeated conversations? | Repeat the saved-initial trajectories | The [five-repetition plan](NEXT_EXPERIMENTS.md#4-repetitions-after-the-first-batch) costs 84,660 target replies and requires a separate budget decision |
| Do the same reasoning patterns hold under adaptive challenges? | Complete reasoning-enabled adaptive coverage with exact challenge logging | Only needed to extend the CoT claims beyond the current static analysis; partial checkpoints are already reported |
| Is the result sensitive to continuation sampling? | A lower-temperature continuation comparison | Keep the saved initial reply fixed; specify model support and budget before any run |

These are alternatives to consider if a specific review question warrants them.
They are not additional required experiments for the current paper. Nationality
and jurisdiction-preserving input extensions remain
[future work](NEXT_EXPERIMENTS.md#5-future-work).
