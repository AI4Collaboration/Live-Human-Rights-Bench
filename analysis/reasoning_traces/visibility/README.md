# Reasoning-text visibility and keyword frequency

Source: `80ea0ffcd8315a0af089ff0c89e2a47ceca53a25`. No model API calls.

This analysis uses only returned reasoning text. It does not report judgment changes or accuracy.

## Visible text and phrase frequency

| Model | Cue | Empty / N | Median visible words, nonempty | Phrase-bearing / nonempty | Occurrences / 1000 words |
|---|---|---:|---:|---:|---:|
| Opus-4.6 | baseline_high | 177/911 | 29 | 15/734 | 0.251 |
| Opus-4.6 | authority_lawyer | 1/911 | 199 | 22/910 | 0.115 |
| Opus-4.6 | authority_researcher | 0/911 | 147 | 79/911 | 0.556 |
| V4-Flash | baseline_high | 0/946 | 94 | 25/946 | 0.200 |
| V4-Flash | authority_lawyer | 0/946 | 149 | 60/946 | 0.361 |
| V4-Flash | authority_researcher | 0/946 | 189 | 201/946 | 1.028 |

## Same-case, equal-window comparison

All windows use the researcher cue. Both models must have at least K words; the eligible subset changes with K. The full-text and prefix comparison within each row always uses the same cases.

| Visible prefix | N | Opus full / prefix | Flash full / prefix | Full / prefix Flash-minus-Opus gap (pp) |
|---|---:|---:|---:|---:|
| 64 words | 749 | 62/18 | 169/4 | 14.3/-1.9 |
| 128 words | 321 | 34/20 | 96/24 | 19.3/1.2 |
| 256 words | 35 | 3/3 | 15/13 | 34.3/28.6 |

Counts are literal phrase detections, not measures of latent evaluation awareness. Prefix truncation measures sensitivity to the analyzed text window; it does not emulate a provider's summary or redaction policy.

## Provider policy and saved-data limits

Anthropic documents summarized thinking for Opus 4.6 and the possibility of safety-redacted blocks. The saved runner keeps readable strings but drops raw provider block metadata. No timestamps, paired raw thinking or redaction-event indicators were saved, so these data cannot establish a policy change or count censorship events. Empty text is recorded as unavailable text, not as proven redaction.

Provider documentation: [Thinking](https://platform.claude.com/docs/en/build-with-claude/thinking). Retrieved and checked on 2026-09-26.

## Reproduction

`python analysis/analyze_trace_visibility.py`

Rules, corpus counts, bootstrap intervals, exact word matching and cohort membership are released alongside this report. Cluster intervals use 5000 source-judgment bootstrap resamples with seed 20260926.
