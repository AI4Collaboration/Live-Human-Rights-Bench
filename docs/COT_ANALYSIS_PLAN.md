# CoT analysis: scope and status

The full-text analysis is complete using existing results. New model runs are
on hold. This planning note is excluded from supplementary submission material.

## Completed analysis

The [full-explanation report](../analysis/reasoning_traces/full_text/README.md)
is the current source for reasoning length and evaluation-language comparisons.
It uses every word of each recorded explanation without a prefix cutoff or
minimum word count.

- Report text availability separately from phrase absence.
- Compare cues on the same instances with text under all three cues.
- Report median and interquartile length, within-instance changes and
  judgment-cluster intervals.
- Report both explanations containing evaluation language and occurrences per
  thousand words; scores do not determine phrase matches.
- Keep the same available instances across all three turns for temporal comparisons.
- Describe associations with judgment changes at the same turn without treating
  verbalized awareness as a mechanism.

The [CoT index](../analysis/reasoning_traces/README.md) also links whole-cohort
reversal statistics, exact phrase evidence and supplementary examples.
The selected examples illustrate recorded responses; they do not establish
how often a semantic reasoning pattern occurs.

## Interpretation and coverage

The researcher cue states a profession rather than announcing an evaluation.
Role identity, explicit evaluation framing and spontaneously verbalized evaluation
awareness are distinct variables. Opus supplies summarized reasoning. The saved
records do not identify redaction events or provide unsummarized counterparts.

These reasoning-enabled runs have fresh initial responses. Do not combine their
scores or text with the main score-only or placebo experiments. Adaptive
checkpoints remain partial and do not retain the generated challenge text.
Later turns replay answer content rather than the saved reasoning fields.

## Deferred work

Explicit evaluation framing remains the two-condition contrast in
[Next experiments](NEXT_EXPERIMENTS.md#3-planned-evaluation-framing-control).
The AI researcher identity is held fixed in both conditions; the standalone
role comparison is [rebuttal-only](REBUTTAL_EXPERIMENTS.md).
Any future collection must retain exact messages, returned reasoning, finish
reasons, model versions, settings and source hashes. Semantic annotation and
new model calls require a separate decision; neither is part of the completed
full-text analysis.
