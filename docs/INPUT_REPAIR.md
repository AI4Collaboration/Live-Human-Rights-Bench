# Input leakage repair and one-summary protocol

The main summarization experiment uses **one summary per judgment**, selected as
original version index 0 before looking at any evaluator's response. That means
947 summary texts covering 1,000 atomic targets. The two
other historical versions are not current experimental inputs.

## What three versions previously meant

The builder made three independent draws with the same summarizer and prompt at
temperature 1.0. They were not three distinct summarization methods. The main
runner evaluated each draw, and analysis scripts support per-version accuracy and
alignment. These capabilities alone do not establish that a cross-version
robustness analysis was completed. No such current-cohort result artifact was
found in the GitHub snapshot `4a1ba11`.

The one-summary protocol does not change the number of repeated answers requested
from a target model. Repeated target answers are a separate factor. Multi-version
generation and evaluation are removed. Faithfulness is investigated with the
[extractive control and atomic coverage instrument](SUMMARIZATION_PROTOCOL.md).

## What is being removed

The scope is the **actual model-visible text**, including the runner's first
50,000 source characters and the complete summary. Remove the current ECtHR
judgment's merits assessment, operative conclusions, and answer-revealing cover
headnotes. Retain allegations, domestic procedural history, generic legal rules,
and decisions from other cases. Remove an earlier-instance outcome from the same
application when a Grand Chamber judgment recounts the Chamber decision on the
scored complaint. This is an input-leakage check, not a test of proprietary
pretraining overlap.

Formal preambles that state how the current Court applies established case-law
are removed too. Four such source prefixes were repaired and re-reviewed after
the initial review, with their corresponding summaries regenerated.

The final release step also removed adjudicated procedural-history outcomes from
11 judgments and 12 case-article instances. The cut removed 2,456 characters and
left every other field and every untouched row unchanged. The same summarizer
then regenerated the 11 affected judgment-level summaries before publication.

The old summary screen exempted an entire summary whenever the source mentioned
any court's finding. A domestic finding could therefore exempt a new sentence
asserting the current ECtHR verdict. This source-wide exemption has been removed.
Flattened headings, short judgments, headnotes, and tables of contents also
defeated the earlier structural checks.

Source repair uses structural boundaries plus grounded review. Factual appendix
columns are recovered from official HUDOC documents when the retained source
refers to a missing table; the current ECtHR's awards and finding columns are
excluded. No new factual narrative is generated during source repair. The final
target audit then resolves every row to one respondent State, one
provision, and one sub-conclusion. Former Article 41 rows are retargeted to verified
merits sub-conclusions. The cohort remains 1,000 rows with the same annual counts.

## Acceptance and provenance

1. Review each distinct model-visible source. Positive flags must quote text that
   actually occurs in the input.
2. Keep original version 0 only when its source input is unchanged and its own
   review is clean. If the source changed or its summary failed, regenerate
   version 0 using the original model, prompt, temperature and input cap.
3. Review each generated candidate. A rejected candidate is not an accepted
   summary. Preserve attempts and raw outputs in the audit checkpoints.
4. Publish only when all 947 sources and 947 selected summaries are accounted for.
   The semantic gate requires exact canonical text and all 1,000 registered atomic targets.
5. Exercise the real runner with a fake transport to verify the exact outgoing
   messages and that the reference label is never inserted into a prompt.

The original input review flagged current-case conclusions or merits reasoning
in **647/1,000 instances (64.7%)**, representing 606/947 judgments. Conclusion
flags cover 612 instances and reasoning flags 600, with overlap. These are
evidence-grounded machine-review positive counts, not fully human-adjudicated
prevalence estimates. The source-change count is different: benign boundary
cleanup and restoration of missing facts also change source text.

Audit evidence lives under `data/audits/leakage_20260915/`. The pinned original
dataset and three-version summaries remain retrievable from Git commit
`4a1ba1117a047dac7553ca2cfd3100a18171a841`. Previously accepted nonzero-version
repair outputs remain audit history, not inputs to the one-version release.

## Offline verification

```bash
python scripts/validate_eval_dataset.py --require-complete
python scripts/verify_model_input_payloads.py
```

The payload verifier uses an in-memory fake transport and makes no model calls. It
imports `openai` because the real runner does, but needs no key.

## Re-running experiments

Use a new output directory for the approved release. Never resume pre-repair
checkpoints, mix old baseline predictions with repaired summary inputs, or
relabel existing metrics as results of the cleaned corpus. The runner rejects
benchmark text that does not match the active semantic cohort and refuses to resume an
unversioned result directory. Historical alternative datasets are not covered by
this release and must not be presented as having passed its review.

The manuscript and its protected Section 3 are not edited by this repair.
