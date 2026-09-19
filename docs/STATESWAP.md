# Summary-based State Swap

The current experiment and country matching were updated in
[`4b231e1`](https://github.com/AI4Collaboration/Live-Human-Rights-Bench/commit/4b231e17e6dd65880e665c5fe298db3862ff5ade).
Its six model checkpoints are in
[`data/experiments/stateswap_summary/`](../data/experiments/stateswap_summary/).
Each contains 4,000 unique target/arm records: 1,000 each for original, US,
Russia and Ukraine. These records cover the canonical 1,000 targets from
947 judgments.

## Inputs and transformation

The runner selects the same reviewed abstractive summary as the summary and
persuasion experiments. It replaces respondent-country names, aliases and
demonyms with the destination country's name and demonym, using case-insensitive
matching. No generation model
is used. The original summary is the matched reference. The case cohort,
summary file and released transformation reconstruct all four input arms.

Reapplying the released rule to every canonical target gives:

| Destination | Text changed | Different respondent and text changed | Same respondent as destination |
| --- | ---: | ---: | ---: |
| US | 998 | 998 | 0 |
| Russia | 973 | 966 | 32 |
| Ukraine | 832 | 832 | 167 |

All counts use 1,000 targets per destination. Seven Russia-arm changes only
normalize the name of the original Russian respondent. The manuscript therefore
uses **800 targets from 757 judgments** with a different respondent and changed
summary text in every destination arm, and valid score means in all four arms
of all six models. This common cohort supports every model/destination contrast.
The text-change-only intersection has 807 targets and serves as a sensitivity
cohort. The source transformation includes aliases such as Moldova, Czech
Republic, UK, Netherlands and Bosnia.

## Published scores

Each input requests ten 0-100 ratings at temperature 1.0. The published rows
store the valid-score mean, prediction and unparsed count. Scores below 40
predict no violation, scores above 60 predict violation, and 40-60 is abstention.

All **24,000** published rows have a valid score mean. DeepSeek V4 Pro reports
6,211 unparsed sample slots among 40,000 requested ratings; none of its 4,000
row means is missing. A missing individual sample and a missing row mean are
different outcomes. Each saved mean averages that row's valid ratings.

The published rows store aggregate results. The manuscript thresholds the saved
means. Current code uses the shared answer parser and the updated country alias
mapping; new runs save individual ratings and raw responses as well.

## New runs

[`experiments/stateswap_summary_run.py`](../experiments/stateswap_summary_run.py)
validates the canonical inputs and binds checkpoints to the inputs and settings.
New rows additionally save `text_changed`, individual `ratings`, raw `responses`,
all parse `response_attempts` and `parse_retry_count`. The run identity records
the country aliases and demonyms along with model, prompt and input hashes.
Use a fresh output directory:

```bash
python experiments/stateswap_summary_run.py \
  --model openai/gpt-5.6-sol --samples 10 --workers 60 \
  --out data/experiments/stateswap_summary_new
```

The old Hugging Face State Swap release remains deprecated. It is unrelated
to these summary-derived arms.
