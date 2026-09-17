# LiveHumanRightsBench evaluation datasets

## Current evaluation pool

The reported full-record, summary, paraphrase and persuasion experiments use
**1,000 target instances from 947 judgments** in
[`data/processed/echr_unified.json`](data/processed/echr_unified.json).
This is the paper's selected sample; the pipeline supports other release sizes
and time windows.

| Year | Instances | Year | Instances | Year | Instances |
| --- | ---: | --- | ---: | --- | ---: |
| 2012 | 67 | 2017 | 67 | 2022 | 68 |
| 2013 | 67 | 2018 | 68 | 2023 | 68 |
| 2014 | 67 | 2019 | 67 | 2024 | 67 |
| 2015 | 68 | 2020 | 67 | 2025 | 67 |
| 2016 | 68 | 2021 | 67 | 2026 | 57 |

Decision dates range from **2012-01-10 to 2026-05-21**. The sample covers
**24 Convention and Protocol provisions**, **46 respondent states**, and
**700 violation / 300 no-violation outcomes**. There are 33 procedural targets
under Articles 34 and 38 and 167 targets involving Ukraine. The partial 2026
window contains the 57 observed targets.

## Target identities and executed questions

The annotation key is
`(item_id, target_respondent_code, article_full, target_issue)`.
Each row stores one verified respondent, provision and sub-conclusion, together
with `target_question` and its reference outcome. Article 41 is excluded as a
binary violation target.

The completed experiments ask the provision-level question shown in the
[README](README.md#benchmark-and-inputs). The atomic fields
retain annotation identity. The executed prompt in each runner determines the
question seen by the model; a stored prompt-version tag alone is insufficient.

## Shared summaries

[`data/processed/summaries_dsv41flash.json`](data/processed/summaries_dsv41flash.json)
contains one selected DeepSeek v4.1 Flash summary for each judgment. Original
version index 0 was selected before evaluation. All targets and models sharing a
judgment receive the same summary.

The extractive control is
[`data/processed/summaries_extractive_leakchecked_20260916.json`](data/processed/summaries_extractive_leakchecked_20260916.json).
Its 947 extracts support the fact-retention comparison. The current manuscript
reports predictive accuracy for full records and abstractive summaries.
[docs/SUMMARIZATION_PROTOCOL.md](docs/SUMMARIZATION_PROTOCOL.md) describes both
summary variants and the selected coverage analysis.

## Frozen release and paired comparisons

The [manifest](configs/evaluation_dataset.json) records target fields, annual
counts, labels and summary coverage. Validate it without model calls:

```bash
python scripts/validate_eval_dataset.py --require-complete
```

Use a fresh output directory whenever inputs, prompts or the release change.
Summary comparisons pair the same targets across full and compressed records;
paraphrases use their own original-input arm. Persuasion pairs static and
adaptive branches from the same decided initial response. The current analysis
rules are in [STATISTICAL_METHODOLOGY.md](STATISTICAL_METHODOLOGY.md).

## State Swap and earlier cohorts

State Swap uses a separate cohort: 816 base cases rendered with the original
respondent, Iceland, Ukraine and Russia, giving 3,264 inputs. Updated results
will fill the manuscript's Metadata heading.

The earlier static-2k and temporal-2k source sets, `livehrb_1k.json` pilot and
141-pair pilot remain historical artifacts. Their original sampling plans and
statistics are recoverable from Git history. Current counts and reported
comparisons are defined by the manifest and experiments above.
