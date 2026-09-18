# Shared summaries and factual coverage

The main experiment uses **one fixed DeepSeek v4.1 Flash summary per judgment**:
947 texts for 1,000 targets. Every evaluating model receives the same selected
text, including all targets sharing a judgment. Original version index 0 was
selected before model evaluation.

| Component | Input and output | Reported measure |
| --- | --- | --- |
| Abstractive summary | Reviewed source to an approximately 500-word summary | Matched prediction accuracy and factual retention |
| Extractive control | Same source to selected verbatim passages | Factual retention and input length |
| Atomic coverage | Shared source claims checked against each summary | Overall and Court-referenced claim retention |

## Completed results

The full-record and abstractive-summary checkpoints cover six models and 1,000
targets per model under `data/experiments/unified_fullcase_latest/`. At a median
24.0% of the original input length, summaries reduce accuracy by 0.9-2.4 percentage
points under the manuscript's mean-score rule.

The released extractive artifact,
`data/processed/summaries_extractive_leakchecked_20260916.json`, contains 947
extracts matching their selected source spans. Its median within-judgment length
ratio is 89.5%. It supplies the retention control in the current manuscript.

The selected claim-level analysis tests both variants against **51,347 identical
claims**, including **19,646 Court-referenced claims from 659 judgments**.
Abstractive summaries retain **12,851 (65.4%)** of the Court-referenced claims;
extractive summaries retain **18,717 (95.3%)**. Qwen3-235B extracts the claims and
checks their support. These checkpoints are completed local analysis artifacts
awaiting publication. The manuscript's source manifest pins their hashes.

## Use the selected summary

```bash
python scripts/validate_eval_dataset.py --require-complete
```

Pass `data/processed/summaries_dsv41flash.json` to the full-case runner's
`--summaries` argument. Use fresh result directories for changed inputs and
compare each summary arm with its matched full-record arm. The current execution
commands are in [README.md](../README.md#setup-and-execution), and the aggregation
rule is in [STATISTICAL_METHODOLOGY.md](../STATISTICAL_METHODOLOGY.md).

## Generate an extractive control for a new run

The span selector takes the reviewed, 50,000-character source input, selects
passages, assembles them in source order and records their paragraph numbers.
Run the format check before making selector calls:

```bash
python -X utf8 scripts/build_extractive.py --cases data/processed/echr_unified.json --summarizer deepseek/deepseek-v4.1-flash --out data/processed/summaries_extractive_new.json --check-only
python -X utf8 scripts/build_extractive.py --cases data/processed/echr_unified.json --summarizer deepseek/deepseek-v4.1-flash --api-key-env OPENROUTER_API_KEY --out data/processed/summaries_extractive_new.json
```

The second command makes model calls. Verify each assembled extract against its
selected source spans and record extraction coverage before analysis.

## Measure atomic coverage for a new run

Set `COVERAGE_MODEL` to the coverage model's provider identifier; the reported
analysis uses `qwen/qwen3-235b-a22b`. Set `FULL_JUDGMENTS_CSV` to the full-judgment
corpus with `item_id` and `full_text` columns. Full judgments identify references
from the Court's reasoning to factual passages. Target models receive the
reviewed factual record or summary.

Run the variants sequentially in the **same new output directory**. The second
variant reuses the first variant's extracted claims, giving a claim-for-claim
comparison. Both commands make model calls.

```bash
python -X utf8 scripts/build_atomic_coverage.py --full-texts "$FULL_JUDGMENTS_CSV" --summaries data/processed/summaries_dsv41flash.json --variant abstractive --model "$COVERAGE_MODEL" --api-key-env OPENROUTER_API_KEY --out data/experiments/atomic_coverage_new
python -X utf8 scripts/build_atomic_coverage.py --full-texts "$FULL_JUDGMENTS_CSV" --summaries data/processed/summaries_extractive_new.json --variant extractive --model "$COVERAGE_MODEL" --api-key-env OPENROUTER_API_KEY --out data/experiments/atomic_coverage_new
```

On PowerShell, use `$env:COVERAGE_MODEL` and `$env:FULL_JUDGMENTS_CSV`.
Each support check receives the selected summary and source claims. Results
record overall and Court-referenced retention with their denominators. Newly
generated outputs define a new analysis version.

## Input provenance

[INPUT_REPAIR.md](INPUT_REPAIR.md) defines source review and shared-summary
selection. The reported experiments use `experiments/run_perturbation_fullcase.py`,
`experiments/paraphrase_run.py` and `experiments/syco_run.py`.
