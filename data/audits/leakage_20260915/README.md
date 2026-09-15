# Evidence for the one-summary input release

The final status, counts and content hashes are recorded in
[`repair_release_report.json`](repair_release_report.json). This folder contains
review and repair evidence, not new target-model evaluation results.

## Original-input review

The reviewer saw the exact first 50,000 characters used by the runner, without
reference labels. Positive decisions require matching verbatim evidence.

| Machine-review category | Judgments | Case-article instances | Instance rate |
| --- | ---: | ---: | ---: |
| Current ECtHR conclusion | 573 | 612 | 61.2% |
| Current ECtHR merits reasoning | 563 | 600 | 60.0% |
| Either category | 606 | 647 | 64.7% |

Categories overlap. These are machine-review positive rates, not fully
human-adjudicated prevalence estimates. The population is the 1,000-instance
`echr_unified.json` cohort, not every historical dataset in this repository.
This review does not measure proprietary pretraining overlap.

## Evidence files

- `original_source_reviews.jsonl`: original source inputs, review outputs and exact evidence.
- `proposed_sources.provenance.json`: source hashes, removed boundaries and recovered factual columns.
- `hudoc_retrieved.jsonl`, `hudoc_restored_extra.jsonl`, `hudoc_source_html.zip`: official-source retrievals and the archived appendix HTML used for reproducible extraction.
- `proposed_source_reviews.jsonl`: reviews bound to each candidate source hash, including superseded candidate versions.
- `manual_adjudications.json`: the documented sparse-facts adjudication for Bellotto. It does not override a conclusion or reasoning flag.
- `residual_assertion_context_review.json`: contextual review of 21 remaining lexical candidates in 20 source documents. These refer to earlier judgments, domestic proceedings, or generic rules.
- `original_summary_reviews.jsonl`: checks of old summaries considered for retention.
- `summary_regeneration*.jsonl`: completed regeneration records and raw candidate/review attempts. Files ending in `.attempts.jsonl` additionally retain events before a task completes.
- `model_input_payload_check.json`: offline inspection of the real runner's outgoing messages, using a fake transport. It is not a model benchmark result.
- `extractive_format_preflight.json`: a separate control-readiness check. Only 385/947 sources satisfy the current numbered-paragraph parser; the remaining 562 are blocked before paid selection. This is not a leakage flag or a faithfulness score.

## Selection and history

The main release selects original version index **0** for every judgment, before
evaluator results are examined. Original-index-0 summaries are retained only if
their actual source input is unchanged and their own review passes. Otherwise
that slot is regenerated and reviewed. No best-of-three selection is performed.

Earlier accepted version-1/version-2 repair outputs remain in the checkpoints as
history but are not published as current inputs. `paused` records mean that queued
work was not completed during a controlled pause; they are not accepted outputs
or model failures. A failed attempt is never counted as an accepted summary.

The original corpus and all three historical summary versions remain in Git
commit `4a1ba1117a047dac7553ca2cfd3100a18171a841`. The source proposal itself is not
duplicated in Git: the publication gate verifies it before it becomes the canonical
dataset. The archive-based source reconstruction was checked to reproduce the
proposal exactly.

```bash
python scripts/publish_leakage_repair.py
python scripts/validate_eval_dataset.py --require-complete
python scripts/verify_model_input_payloads.py
```

Do not reuse pre-repair target-model results or checkpoints for this input release.
