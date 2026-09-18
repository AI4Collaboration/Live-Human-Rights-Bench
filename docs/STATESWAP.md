# Summary-based State Swap

The current experiment was released in
[`cc59734`](https://github.com/AI4Collaboration/Live-Human-Rights-Bench/commit/cc59734).
Its six model checkpoints are in
[`data/experiments/stateswap_summary/`](../data/experiments/stateswap_summary/).
Each contains 4,000 unique target/arm records: 1,000 each for original, US,
Russia and Ukraine. These records cover the canonical 1,000 targets from
947 judgments.

## Inputs and transformation

The runner selects the same reviewed abstractive summary as the summary and
persuasion experiments. It replaces literal respondent-country names and
demonyms with the destination country's name and demonym. No generation model
is used. The original summary is the matched reference. The case cohort,
summary file and released transformation reconstruct all four input arms.

Reapplying the released rule to every canonical target gives:

| Destination | Text changed | Same respondent as destination | Other unchanged inputs |
| --- | ---: | ---: | ---: |
| US | 891 | 0 | 109 |
| Russia | 859 | 32 | 109 |
| Ukraine | 725 | 167 | 108 |

All counts use 1,000 targets per destination. The other unchanged inputs include
country-name aliases that the literal rule does not match. For the US arm,
these include 38 Moldova, 19 Czechia, 17 United Kingdom, 16 Netherlands and
15 Bosnia and Herzegovina targets. Some summaries contain no matching country
name or demonym. An arm label alone therefore does not establish a text change.
Use the reconstructed text-change indicator when analyzing actual interventions.

## Published scores

Each input requests ten 0-100 ratings at temperature 1.0. The published rows
store the valid-score mean, prediction and unparsed count. Scores below 40
predict no violation, scores above 60 predict violation, and 40-60 is abstention.

DeepSeek V4 Pro has 67 of 4,000 rows with no valid score and reports 6,042
unparsed ratings among 40,000 requested ratings. Every other model has a
non-null mean in all 4,000 rows. Keep failed predictions separate from
abstentions and strict reversals.

The published runner parsed the first standalone integer. Its raw responses
were not saved, so these stored means cannot be reparsed. Current code uses the
shared answer parser, which rejects article numbers and API errors as scores.
The input transformation and question text remain unchanged.

## New runs

[`experiments/stateswap_summary_run.py`](../experiments/stateswap_summary_run.py)
validates the canonical inputs and binds checkpoints to the inputs and settings.
New rows additionally save `text_changed`, individual `ratings` and raw
`responses`. Use a fresh output directory:

```bash
python experiments/stateswap_summary_run.py \
  --model openai/gpt-5.6-sol --samples 10 --workers 60 \
  --out data/experiments/stateswap_summary_new
```

The old Hugging Face State Swap release remains deprecated. It is unrelated
to these summary-derived arms.
