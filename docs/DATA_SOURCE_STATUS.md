# Data source status and deprecated releases

Updated **18 September 2026**. Repository inspection baseline:
[`d5b2879`](https://github.com/AI4Collaboration/Live-Human-Rights-Bench/commit/d5b2879be6dce821e5de0124ceab4997aff41c33).
Exact revisions, file hashes and replacements are recorded in
[`configs/data_source_status.json`](../configs/data_source_status.json).

**Use the current GitHub inputs below for the reported experiments. The six
legacy Hugging Face sources listed here are deprecated as evaluation inputs.**
Their old releases remain useful for provenance and historical reproduction.
An upstream source pool can supply candidates for a new release, after source
review and target resolution.

## Current inputs

| Status | Artifact | Role |
| --- | --- | --- |
| **CURRENT** | [`echr_unified.json`](../data/processed/echr_unified.json) | 1,000 targets from 947 judgments; canonical full-case input |
| **CURRENT** | [`summaries_dsv41flash.json`](../data/processed/summaries_dsv41flash.json) | 947 selected abstractive summaries; summary evaluation and sycophancy input |
| **CURRENT** | [`summaries_extractive_leakchecked_20260916.json`](../data/processed/summaries_extractive_leakchecked_20260916.json) | 947 extractive controls |
| **PENDING PUBLICATION** | `data/processed/echr_stateswap.json` | Input for the updated State Swap run; absent from the inspected GitHub commit |
| **PENDING PUBLICATION** | `data/processed/paraphrase_pairs.json` | Generated inputs for the published paraphrase results; absent from the inspected GitHub commit |

The current dataset contract is [`evaluation_dataset.json`](../configs/evaluation_dataset.json).
The source-status registry identifies releases; it is not a new semantic audit.
No Hugging Face mirror of the current input release is designated by this record.

## Deprecated Hugging Face sources

All repository IDs below belong to `overthelex`. Links pin the Hub revision
observed on 18 September 2026, rather than a moving `main` branch.

| Status | Dataset and pinned revision | Historical role | Current replacement or disposition |
| --- | --- | --- | --- |
| **DEPRECATED** | [`echr-verdict-free` @ `f897bd6`](https://huggingface.co/datasets/overthelex/echr-verdict-free/tree/f897bd6b1897b522d89540c53cecc2e8df06daa8) | General source pool | Use `echr_unified.json` for current evaluation; source pool remains candidate material for ingestion |
| **DEPRECATED** | [`echr-ukr-verdict-free` @ `3d38807`](https://huggingface.co/datasets/overthelex/echr-ukr-verdict-free/tree/3d388078c3627814b11cf6dbd87de0def8d032b9) | Ukraine source pool | Same current replacement; candidate material for ingestion |
| **DEPRECATED** | [`echr-livehrb-static-2k` @ `ee9cb87`](https://huggingface.co/datasets/overthelex/echr-livehrb-static-2k/tree/ee9cb87f74c6843bec44f4eb33bc4151bbcfea49) | Old 2,000-row static set; source for earlier State Swap and MFT inputs | Use the current release; old derivatives do not inherit its review |
| **DEPRECATED** | [`echr-livehrb-temporal-2k` @ `24dff82`](https://huggingface.co/datasets/overthelex/echr-livehrb-temporal-2k/tree/24dff82a53c61fa298c0ee39841c67ea9ed0fd44) | Old 2,000-row temporal set | Use the current release and its target contract |
| **DEPRECATED** | [`echr-livehrb-temporal-1k` @ `b7cc10b`](https://huggingface.co/datasets/overthelex/echr-livehrb-temporal-1k/tree/b7cc10be36c0a8be879217c8c6b0bb9791bd5fb7) | Source used by the old `livehrb_1k.json` importer | Use `echr_unified.json`; the committed old import has 1,212 rows |
| **DEPRECATED** | [`echr-livehrb-stateswap` @ `4360866`](https://huggingface.co/datasets/overthelex/echr-livehrb-stateswap/tree/4360866441dc7da39df442d16de2fbc46d29119e) | Earlier State Swap corpus: 816 case-article base groups and four arms | Updated input and its provenance are pending publication; there is no designated current replacement yet |

These are project-level deprecation labels recorded in GitHub. They do not
change the Hub repositories. Future rebuilt releases need their own pinned
revision and review record before being designated current here. The historical
audit files do not pin every audited local export to a Hub revision; their
counts must remain attached to their recorded local input hashes.

## Deprecated local inputs and results

| Status | Artifact | Replacement or disposition |
| --- | --- | --- |
| **DEPRECATED** | [`livehrb_1k.json`](../data/processed/livehrb_1k.json), 1,212 rows | `echr_unified.json` |
| **DEPRECATED** | [`echr_cases_final_clean.json`](../data/processed/echr_cases_final_clean.json), 141 rows | `echr_unified.json` |
| **DEPRECATED** | [`test_20_cases.json`](../data/processed/test_20_cases.json), 20 rows | Historical fixture only; use an explicitly selected subset of the current release for new checks |
| **DEPRECATED** | Pre-repair `echr_unified.json` and three-version summaries at [`4a1ba11`](https://github.com/AI4Collaboration/Live-Human-Rights-Bench/commit/4a1ba1117a047dac7553ca2cfd3100a18171a841) | Current canonical files above; retain old versions as repair evidence |
| **HISTORICAL** | `data/experiments/stateswap/`, `metadata/data/eval/`, `paraphrase/data/eval/`, `time_bin_contamination/data/eval/` | Earlier protocols; current result directories are listed in the [README](../README.md#current-release) |

Names such as `verdict-free`, `final_clean`, or `1k` identify old artifacts;
they do not establish current approval, current row counts, or source repair.

## What the historical leakage records mean

The [other-corpora audit](../data/audits/other_corpora/README.md) records
**286 of 816** State Swap base texts and **884 of 2,000** static-set texts with
remaining detector `leak` flags after a local Registry-headnote strip. Its
status is `CANDIDATES_WITH_EVIDENCE_NOT_AN_ADJUDICATED_RATE`. These are historical
candidate counts, not current-cohort leakage rates or proof that a repaired
version was published to the Hub.

The relevant leakage is disclosure of the **judgment being predicted**, through
its merits reasoning, final conclusion, or an answer-revealing headnote.
Earlier decisions, other cases and domestic proceedings can be legitimate
pre-decision information. An earlier Chamber decision in the same application
does not by itself reveal the later Grand Chamber decision. The September repair
used a stricter exclusion rule for some earlier-instance outcomes; that historical
choice is documented in [INPUT_REPAIR.md](INPUT_REPAIR.md), rather than treated
as proof that any retained earlier decision leaks the current answer.

## Importers and builders that still refer to old sources

| Entry points under `scripts/` | Status and intended use |
| --- | --- |
| `build_livehrb_input.py` | Legacy temporal-1k importer; does not build the current release |
| `build_contamination_input.py` | Legacy static-2k format adapter; field renaming does not repair source text |
| `build_stateswap_input.py` | Legacy State Swap format adapter; copies `case_text_rendered` and does not run source repair |
| `generate_state_swap.py`, `push_stateswap.py`, `recut_stateswap.py`, `build_human_validation_subset.py` | Earlier State Swap generation, publication and validation tooling tied to legacy Hub sources |
| `build_livehrb_static.py`, `build_temporal_split.py`, `build_cutoff_partitions.py` | Earlier source-set and partition builders |
| `build_unified_set.py` | Historical candidate sampler using local `echr_livehrb_static_2k.json`; sampling alone does not recreate the reviewed current release |
| `hudoc_live_refresh.py`, `build_stratified_sample.py` and metadata backfill tools | Candidate ingestion or preparation; review sources and targets before admitting their output to a release |

These labels document source status; existing script defaults are retained for
historical reproduction. `hudoc_live_refresh.py --full-pipeline` processes newly
fetched judgments and preserves existing records, so it does not retroactively
repair an old source corpus. See [PIPELINE.md](../PIPELINE.md) for release steps.

For an updated State Swap release, publish the actual input, base-group and arm
identities, source revision, text hashes and review evidence together with the
new results. Review both rendered and templated text if both are distributed.
