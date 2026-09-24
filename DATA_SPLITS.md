# LiveHumanRightsBench evaluation datasets

## Current evaluation pool

The full-record, summary, paraphrase, Country Swap and adversarial-opinion experiments use
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

The completed Türkiye and UK follow-ups each contain 12,000 records for
GPT-4o mini, GPT-4.1 mini and GPT-5.6-sol. Their original common comparison
has 768 targets from 725 judgments. The automated context screen retains
574 targets from 545 judgments for these follow-ups and 606 targets from
577 judgments for the original six-model grid. The full results remain
available; every effect uses its own run's original-summary arm.

The [source-status register](docs/DATA_SOURCE_STATUS.md) lists all deprecated
releases and their replacements. Superseded local input files and results have
been removed. Current counts and comparisons are defined by the manifest above.
