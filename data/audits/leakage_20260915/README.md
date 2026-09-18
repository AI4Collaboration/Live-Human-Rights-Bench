# Evidence underlying the current input release

The released inputs use one selected summary for each of 947 judgments.
[`repair_release_report.json`](repair_release_report.json) records source and
summary hashes together with their acceptance evidence. The current target
identities are verified in [`target_scope_audit.json`](../target_scope_audit.json).

## Evidence files

- `proposed_sources.provenance.json`: source hashes, boundaries and recovered
  factual columns.
- `hudoc_retrieved.jsonl`, `hudoc_restored_extra.jsonl`, `hudoc_source_html.zip`:
  official-source retrieval evidence and factual appendix material.
- `original_source_reviews.jsonl`, `proposed_source_reviews.jsonl`: reviews
  bound to source text hashes.
- `manual_adjudications.json`, `residual_assertion_context_review.json`:
  contextual decisions for flagged source passages.
- `original_summary_reviews.jsonl`, `summary_regeneration*.jsonl`: summary
  review and generation evidence supporting accepted outputs. Attempt records
  are not accepted summaries.

Use the current input hashes in the
[source inventory](../../../configs/data_source_status.json) to identify the
published texts. The [input-review protocol](../../../docs/INPUT_REPAIR.md)
describes source attribution, summary selection and release checks.
