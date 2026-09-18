# Input review and shared-summary protocol

## Current inputs

The release contains **1,000 targets from 947 judgments**, with one selected
DeepSeek v4.1 Flash abstractive summary per judgment. All targets sharing a
judgment use the same summary. Original version index 0 was fixed before target
model evaluation; summaries are not selected using evaluator scores.

The [source inventory](DATA_SOURCE_STATUS.md) identifies the current files,
exact hashes, deprecated sources and pending inputs. Current execution commands
are in the [README](../README.md#setup-and-execution).

## Review scope

Review the actual model-visible source and summary. Source review covers the
runner's first 50,000 characters; summary review covers the complete selected
summary. Exclude the predicted judgment's merits reasoning, final conclusions
and answer-revealing headnotes.

Earlier decisions, domestic proceedings, allegations and general legal rules
can be legitimate pre-decision information. An earlier Chamber outcome is not
by itself disclosure of a later Grand Chamber answer. Attribute each flagged
passage to the judgment being predicted before deciding whether to remove it.

Resolve every target to its respondent, provision and sub-conclusion. Article 41
is not a binary violation target. The dataset retains the verified target identity;
the runner's actual prompt determines the question seen by the model.

## Acceptance and provenance

1. Record source text hashes and review evidence for each judgment. Positive
   flags must quote text that occurs in the model input.
2. Retain a selected summary only when its source and its own review pass.
   Regenerate affected summaries using the same model and generation settings.
3. Record generation attempts and reviews separately from accepted outputs.
4. Verify all 947 source texts and selected summaries against the released files.
   Check the 1,000 target identities against the target audit.
5. Verify extractive summaries against their selected verbatim source spans.

The input evidence is in [`data/audits/`](../data/audits/), including
[source provenance and review records](../data/audits/leakage_20260915/),
[located span evidence](../data/audits/verdict_spans/) and the
[target audit](../data/audits/target_scope_audit.json).
[SUMMARIZATION_PROTOCOL.md](SUMMARIZATION_PROTOCOL.md) describes the summary
comparison and factual-coverage analysis.

## Release checks and evaluation

```bash
python scripts/validate_eval_dataset.py --require-complete
```

The validator checks the cohort, target identities and summary coverage without
calling models. Semantic review uses the source and summary evidence above.
Run evaluations in new output directories whenever inputs or prompts change,
with the input identity recorded alongside each result.
