# Summary-based Country Swap

The original six-model experiment and country matching were updated in
[`4b231e1`](https://github.com/AI4Collaboration/Live-Human-Rights-Bench/commit/4b231e17e6dd65880e665c5fe298db3862ff5ade).
Its six model checkpoints are in
[`data/experiments/stateswap_summary/`](../data/experiments/stateswap_summary/).
Each contains 4,000 unique target/arm records: 1,000 each for original, US,
Russia and Ukraine. These records cover the canonical 1,000 targets from
947 judgments.

## Inputs and transformation

The runner selects the same reviewed abstractive summary as the summary and
adversarial opinion experiments. It replaces respondent-country names, aliases and
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
normalize the name of the original Russian respondent. The unfiltered comparison
uses **800 targets from 757 judgments** with a different respondent and changed
summary text in every destination arm, and valid score means in all four arms
of all six models. This common cohort supports every original six-model/destination contrast.
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

## Türkiye follow-up

The [21 September release](https://github.com/AI4Collaboration/Live-Human-Rights-Bench/commit/b35f6ca1b97017175fab7d9862d29a057529ec2f)
adds original, Türkiye, Russia and Ukraine arms for GPT-4o mini, GPT-4.1 mini
and GPT-5.6-sol in `data/experiments/stateswap_summary_turkey/`. The three runs
share the v1.0 input hashes, summaries and scoring settings. All 12,000 records
have ten parsed ratings; their raw responses, parse histories, stored means and
transformation flags pass the [offline audit](../analysis/stateswap_turkey/REPORT.md).

Actual respondent substitutions number 983 for Türkiye, 966 for Russia and 832
for Ukraine. The common comparison uses **785 targets from 742 judgments**,
excluding original respondents equal to any destination and requiring changed
text in all three arms. The 15-target difference from the US cohort consists
of original Türkiye cases, not missing scores.

Russia and Ukraine shifts are positive for both earlier GPT mini models and
negative for GPT-5.6-sol, including after correction across nine effects.
The follow-up replaces the US destination under the existing prompt.

## UK follow-up and combined comparison

Revision `05b96bf` adds original, UK, Russia and Ukraine arms for GPT-4o mini,
GPT-4.1 mini and GPT-5.6-sol. All 12,000 records and 120,000 final ratings pass
the [offline audit](../analysis/stateswap_uk/REPORT.md). The run uses the same
v1.0 input hashes and scoring prompt as the Türkiye follow-up. The UK
replacement is `the United Kingdom` / `British`.

Actual substitutions affect 981 UK targets. Requiring substitutions under UK,
Russia and Ukraine leaves 783 targets from 740 judgments. On this cohort,
UK substitution lowers mean violation likelihood by 1.32, 3.06 and 2.01
points for GPT-4o mini, GPT-4.1 mini and GPT-5.6-sol. All three effects remain
negative after correction across nine comparisons.

The unfiltered [combined follow-up comparison](../analysis/stateswap_followups/REPORT.md)
retains all eighteen effects from both runs. It uses 768 targets from 725
judgments with actual substitutions in all four destination countries. Each
effect uses its run's own original arm. The repeated Russia and Ukraine
conditions remain separate. Pointwise intervals use 2,000 judgment-cluster
bootstrap draws; the joint eighteen-effect family uses 20,000 draws. The
original US comparison and the individual follow-up cohorts remain available.

The UK run adds a destination under the existing prompt. A comparison holding
Convention applicability fixed remains [future work](NEXT_EXPERIMENTS.md#country-swap).
No further destination grid is scheduled.

## Context check and new runs

Country Swap now excludes summaries flagged for environmental context,
cross-border events, territorial disputes or a destination already present
in the original text. It also excludes unchanged inputs and unresolved
respondents. The [audit](../analysis/stateswap_context/REPORT.md) gives exact
rules and examples. These deterministic checks identify contexts to exclude;
they do not certify all remaining local institutions or legal relationships.

Applying the check to saved results retains **606 targets from 577 judgments**
for the original US comparison and **574 targets from 545 judgments** for the
shared follow-ups. These are the screened manuscript comparisons. The full
cohorts above remain available as source results.

The runner writes `context_manifest.json` before scoring, recording input hashes,
eligibility and exclusion reasons for every target. New checkpoints use
`country-swap-summary-context-v3` and cannot resume older unscreened runs.
No original reference verdict is used to score a substituted arm's accuracy.

Preview the shared follow-up cohort without an API key or model calls:

```bash
python experiments/stateswap_summary_run.py \
  --model openai/gpt-5.6-sol --targets uk --validity-targets uk turkey \
  --preflight-only --out data/experiments/country_swap_context_checked
```

Omit `--preflight-only` only when a new run is authorized. Use the same
`--validity-targets` for runs that will share a comparison cohort. Existing
results can be analyzed offline with `python analysis/stateswap_context/audit.py`.
Historical `stateswap_*` filenames are retained so source references resolve.
The deprecated Hugging Face release is not an evaluation input.
