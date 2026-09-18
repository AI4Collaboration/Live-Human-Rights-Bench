# Data inventory

Updated **18 September 2026**. The [source-status register](../docs/DATA_SOURCE_STATUS.md)
and [machine-readable inventory](../configs/data_source_status.json) identify
current inputs, deprecated releases and pending artifacts.

## Current inputs

| Artifact | Contents | Use |
| --- | --- | --- |
| [`processed/echr_unified.json`](processed/echr_unified.json) | 1,000 targets / 947 judgments | Canonical case input |
| [`processed/summaries_dsv41flash.json`](processed/summaries_dsv41flash.json) | 947 selected abstractive summaries | Summary evaluation and sycophancy |
| [`processed/summaries_extractive_leakchecked_20260916.json`](processed/summaries_extractive_leakchecked_20260916.json) | 947 extractive summaries | Extractive control |

Target definitions and counts are in the [dataset contract](../DATA_SPLITS.md).
Preparation evidence is in [`audits/`](audits/).

## Deprecated inputs

| Artifact | Status | Replacement |
| --- | --- | --- |
| [`processed/livehrb_1k.json`](processed/livehrb_1k.json), 1,212 rows | **DEPRECATED** | `processed/echr_unified.json` |
| [`processed/echr_cases_final_clean.json`](processed/echr_cases_final_clean.json), 141 rows | **DEPRECATED** | `processed/echr_unified.json` |
| [`processed/test_20_cases.json`](processed/test_20_cases.json), 20 rows | **DEPRECATED**; historical fixture | Explicit subset of the current dataset for new checks |

The six legacy Hugging Face sources are also **deprecated as evaluation inputs**.
See the [pinned inventory](../docs/DATA_SOURCE_STATUS.md#deprecated-hugging-face-sources)
for their roles, revisions and replacements. Retained historical data and audit
records do not inherit the current release's approval.

## Experiment outputs and pending inputs

The current result directories are `experiments/unified_fullcase_latest/`,
`experiments/paraphrase/` and `experiments/syco_full_latest/`.
Their protocols and analysis cohorts are documented in the
[repository README](../README.md#experiments).

The generated paraphrase input `processed/paraphrase_pairs.json` is not committed.
The updated State Swap input `processed/echr_stateswap.json` and updated results
are pending publication. `experiments/stateswap/` contains earlier results.
The historical 816 base groups and 3,264 rendered State Swap rows describe the
old release, not the unpublished updated input.
