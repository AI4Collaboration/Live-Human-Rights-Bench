# Current and deprecated data sources

Updated **18 September 2026**. Exact revisions and current input hashes are in
[`configs/data_source_status.json`](../configs/data_source_status.json).

## Current inputs

| Artifact | Contents | Use |
| --- | --- | --- |
| [`echr_unified.json`](../data/processed/echr_unified.json) | 1,000 targets / 947 judgments | Canonical full-case evaluation input |
| [`summaries_dsv41flash.json`](../data/processed/summaries_dsv41flash.json) | 947 selected abstractive summaries | Summary evaluation and sycophancy |
| [`summaries_extractive_leakchecked_20260916.json`](../data/processed/summaries_extractive_leakchecked_20260916.json) | 947 extractive controls | Factual-retention comparison |

The current target contract is
[`evaluation_dataset.json`](../configs/evaluation_dataset.json).
No Hugging Face mirror is designated for this release.

## Deprecated Hugging Face releases

**DEPRECATED means: do not use these releases as inputs to current evaluations.**
Use the replacement specified below. The links identify the exact deprecated
Hub revisions; they do not designate future releases from the same repository.

| Deprecated dataset | Revision | Use instead |
| --- | --- | --- |
| [`overthelex/echr-verdict-free`](https://huggingface.co/datasets/overthelex/echr-verdict-free/tree/f897bd6b1897b522d89540c53cecc2e8df06daa8) | `f897bd6` | `data/processed/echr_unified.json` |
| [`overthelex/echr-ukr-verdict-free`](https://huggingface.co/datasets/overthelex/echr-ukr-verdict-free/tree/3d388078c3627814b11cf6dbd87de0def8d032b9) | `3d38807` | `data/processed/echr_unified.json` |
| [`overthelex/echr-livehrb-static-2k`](https://huggingface.co/datasets/overthelex/echr-livehrb-static-2k/tree/ee9cb87f74c6843bec44f4eb33bc4151bbcfea49) | `ee9cb87` | `data/processed/echr_unified.json` |
| [`overthelex/echr-livehrb-temporal-2k`](https://huggingface.co/datasets/overthelex/echr-livehrb-temporal-2k/tree/24dff82a53c61fa298c0ee39841c67ea9ed0fd44) | `24dff82` | `data/processed/echr_unified.json` |
| [`overthelex/echr-livehrb-temporal-1k`](https://huggingface.co/datasets/overthelex/echr-livehrb-temporal-1k/tree/b7cc10be36c0a8be879217c8c6b0bb9791bd5fb7) | `b7cc10b` | `data/processed/echr_unified.json` |
| [`overthelex/echr-livehrb-stateswap`](https://huggingface.co/datasets/overthelex/echr-livehrb-stateswap/tree/4360866441dc7da39df442d16de2fbc46d29119e) | `4360866` | **Pending:** updated State Swap input and review evidence |

The source pools may supply candidates for a new benchmark release. Those
candidates require source review and target resolution before evaluation.
The deprecated labels are recorded here in GitHub; the Hub datasets remain
external repositories.

## Deprecated files removed from this repository

| Removed input | Use instead |
| --- | --- |
| `data/processed/livehrb_1k.json` | `data/processed/echr_unified.json` |
| `data/processed/echr_cases_final_clean.json` | `data/processed/echr_unified.json` |
| `data/processed/test_20_cases.json` | An explicitly selected subset of the current dataset |

Obsolete result directories, audit snapshots and archived trial programs have
also been removed. The repository no longer distributes them as supporting
records for the current release. The current result directories are
`data/experiments/unified_fullcase_latest/`, `data/experiments/paraphrase/`
and `data/experiments/syco_full_latest/`.

The source importers `build_livehrb_input.py`, `build_contamination_input.py`
and `build_stateswap_input.py` still refer to deprecated Hub releases. They are
not entry points for reconstructing the current reviewed input. Renaming fields
or importing a Hub export does not perform source review.

## Pending inputs

| Artifact | Status |
| --- | --- |
| `data/processed/echr_stateswap.json` | Updated State Swap input and review evidence pending publication; no current replacement for the deprecated Hub release is designated |
| `data/processed/paraphrase_pairs.json` | Generated inputs for the published paraphrase results pending publication |

Publish updated inputs with their exact source revision, text hashes and review
evidence. New State Swap results must identify their actual base groups and arms.
