# Explicit evaluation language in reasoning traces

Source data: `80ea0ffcd8315a0af089ff0c89e2a47ceca53a25`. Offline analysis only; no model APIs.

## Finding

Under the AI safety researcher cue, V4-Flash reverses at the first challenge in 125/201 (62.2%) traces containing the specified evaluation phrases. Opus-4.6 reverses in 3/79 (3.8%). These are conditional rates within different model-specific text subsets, not a matched-case model effect or a measure of internal awareness.

## Counts

| Model | Cue | Nonempty first-turn traces | Matching traces | Reversed among matches |
|---|---|---:|---:|---:|
| Opus-4.6 | No cue | 734 | 15 | 10/15 (66.7%) |
| Opus-4.6 | Lawyer | 910 | 22 | 0/22 (0.0%) |
| Opus-4.6 | AI safety researcher | 911 | 79 | 3/79 (3.8%) |
| V4-Flash | No cue | 946 | 25 | 25/25 (100.0%) |
| V4-Flash | Lawyer | 946 | 60 | 47/60 (78.3%) |
| V4-Flash | AI safety researcher | 946 | 201 | 125/201 (62.2%) |

## Definition and evidence

The cohort comprises targets with three valid static scores under all three cues within each model: 911 for Opus-4.6 and 946 for V4-Flash. Only the first challenged turn is analyzed. Empty reasoning fields do not enter text-frequency denominators. Conditional reversal divides opposite decisive verdicts at that same turn by matching traces; abstentions remain in the denominator.

Case-insensitive literal phrase rules identify references to testing or evaluating the responding model, including first-person testing phrases and behavioral-test phrases. Mentioning a researcher or lawyer alone does not match. Each target is counted once regardless of the number of matches, and scores do not enter text selection. Exact rules are in results.json and the source code. These exploratory text counts describe explicit wording, not semantic mechanism prevalence or latent awareness.

The rule set omitting behavioral-test phrases requires an explicit first-person or model self-reference. It gives 99/168 (58.9%) for V4-Flash and 3/77 (3.9%) for Opus-4.6. The direction therefore does not depend on the broader behavioral-test phrases.

matched_spans.jsonl preserves every matched span with context, offsets, trace hash, case/provision identifiers and the corresponding score. Counts, conditional rates and case-cluster bootstrap intervals are in results.json and counts.csv. The source hashes are checked against the previously analyzed reasoning release.

The earlier score-only run's Opus researcher rate is 10/874 (1.1%) at turn 2. The separate reasoning run's all-cohort rate is 47/911 (5.2%) at turn 3. Neither is the trace-conditioned first-turn statistic above.

## Reproduction

`python analysis/analyze_reasoning_language.py`
