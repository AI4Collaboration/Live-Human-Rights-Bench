# Data inventory

## Current inputs

| Artifact | Contents | Use |
| --- | --- | --- |
| [`processed/echr_unified.json`](processed/echr_unified.json) | 1,000 targets / 947 judgments | Canonical case input |
| [`processed/summaries_dsv41flash.json`](processed/summaries_dsv41flash.json) | 947 selected abstractive summaries | Summary evaluation and sycophancy |
| [`processed/summaries_extractive_leakchecked_20260916.json`](processed/summaries_extractive_leakchecked_20260916.json) | 947 extractive summaries | Extractive control |

Target definitions are in the [dataset contract](../DATA_SPLITS.md).
Current input evidence is in [`audits/`](audits/).

## Deprecated sources

The six superseded Hugging Face releases are **deprecated as evaluation inputs**.
The local pilot inputs, obsolete results and audit snapshots have been removed.
See the [deprecated-source list](../docs/DATA_SOURCE_STATUS.md#deprecated-hugging-face-releases)
for exact versions and replacements, or its
[JSON inventory](../configs/data_source_status.json).

## Results and pending inputs

Current results are in `experiments/unified_fullcase_latest/`,
`experiments/paraphrase/` and `experiments/syco_full_latest/`.
Protocols and analysis cohorts are in the [README](../README.md#experiments).

The generated `processed/paraphrase_pairs.json` inputs await publication.
Summary-based Country Swap results are released in `experiments/stateswap_summary/`
and `experiments/stateswap_summary_turkey/`. Their transformed inputs are
reconstructed from the canonical summaries and published replacement rule;
`processed/echr_stateswap.json` is not an input to these experiments. The
[Türkiye audit](../analysis/stateswap_turkey/REPORT.md) verifies all 12,000 new
records and their shared 785-target comparison.
