# Quality control

Checks on the two text perturbations, kept separate because they test different
things: a summary is supposed to drop material, a paraphrase is not.

## Summarization

The summary arm's checks live elsewhere in the repository; this table points to them.

| Check | Where |
| --- | --- |
| Protocol, claim retention and extractive control | [docs/SUMMARIZATION_PROTOCOL.md](../docs/SUMMARIZATION_PROTOCOL.md) |
| Extractive control texts | [data/processed/summaries_extractive_leakchecked_20260916.json](../data/processed/summaries_extractive_leakchecked_20260916.json) |
| Claim-level coverage script | [scripts/build_atomic_coverage.py](../scripts/build_atomic_coverage.py) |
| Human validation of the back-reference mapping | [docs/ANNOTATION.md](../docs/ANNOTATION.md), [data/annotation/annotation_merged.csv](../data/annotation/annotation_merged.csv) |
| Variability across summary samples | [analysis/summary_variability/REPORT.md](../analysis/summary_variability/REPORT.md) |

The claim-level checkpoints (51,347 claims) are not in the repository yet; see
the protocol document.

## Paraphrasing

| Check | Where |
| --- | --- |
| Fact preservation (numbers, dates, application numbers, names) | [paraphrase/REPORT.md](paraphrase/REPORT.md) |
| Per-target results | [paraphrase/per_row.csv](paraphrase/per_row.csv), [paraphrase/summary.json](paraphrase/summary.json) |
| Script | [paraphrase/check_preservation.py](paraphrase/check_preservation.py) |
| Claim-level retention (relations, facts without numbers) | [paraphrase/REPORT.md](paraphrase/REPORT.md#claim-level-check), [paraphrase/claims/](paraphrase/claims/) |
| Generator-exclusion check | [analysis/generator_exclusion/paraphrase_strength.csv](../analysis/generator_exclusion/paraphrase_strength.csv) |
