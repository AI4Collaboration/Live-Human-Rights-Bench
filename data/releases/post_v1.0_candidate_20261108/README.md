# Post-v1.0 candidate cohort (frozen 8 November 2026)

Data handoff for EmoP-5 in `docs/rebuttal/DELEGATED_TASKS.md`. This is a candidate
cohort, not a published release. It was frozen before any target-model call.
No result on these judgments exists yet. `configs/` and the v1.0 inputs are unchanged.

## Contents

| File | Purpose |
| --- | --- |
| `cases.json` | 100 verified atomic targets, one per judgment |
| `summaries.json` | One DeepSeek v4.1 Flash summary per judgment |
| `evaluation_dataset.json` | Cohort specification for the validator |
| `core_50.json` | Starting cohort: 15 no-violation and 35 violation judgments |
| `release_manifest.json` | Retrieval date, HUDOC query, seed, selection rule, hashes |
| `target_audit.json` | Official HUDOC holding behind each target |
| `non_overlap_report.json` | Overlap check against v1.0 |
| `exclusions.json` | Funnel and the reason for every excluded judgment |
| `distribution_report.json` | Class, provision, month and respondent counts, with v1.0 |
| `source_reviews2.jsonl`, `summaries.jsonl`, `summaries.attempts.jsonl` | Review and generation records |
| `repair_provenance.json`, `selection_plan.json`, `hudoc_meta_retrieved.json` | Source repair, ranking and retrieved metadata |
| `tools/` | Scripts that produced this cohort |

```bash
python scripts/validate_eval_dataset.py \
  --manifest data/releases/post_v1.0_candidate_20261108/evaluation_dataset.json \
  --require-complete
```

The validator is a structural check and does not establish semantic correctness.

## Construction

HUDOC returned 356 English judgments dated from 22 May 2026, retrieved on
8 November 2026. Candidates came from `scripts/hudoc_live_refresh.py` on a pinned copy
of v1.0. The September input-repair tools were recovered from commit `fa81891`
(`archive/input_repair_20260915/scripts`) because the refresh alone keeps the official
cover-page headnotes, which reveal the outcome:

- Targets: `conclusion_holdings` and `candidates` from `rebuild_atomic_eval_set.py`.
  The parser reproduces 995 of the 1,000 v1.0 targets; the other five are manual overrides.
- Sources: `leak_audit.boundaries.repair` and `leak_audit.factual_tables.extract`.
- Source and summary review: the `review_input_leakage.py` prompt, DeepSeek v4.1 Flash.
- Summaries: `resummarize.generate`, prompt version `leak-safe-v3`, reviewed by
  DeepSeek v4.1 Flash, which is not one of the evaluated models.

Generation and review cost $1.33 on OpenRouter.

## Selection rule

One target per judgment, ranked by SHA-256 of seed `20261108` and the identifiers.
The no-violation stratum takes up to 30 judgments. The violation stratum takes 70,
allocated across decision months in proportion to eligible judgments. Next-ranked
judgments in the same stratum substitute for failed summaries. Selection used no
model prediction.

The 70/30 split matches v1.0 and is deliberately enriched: only 37 of 259 eligible
judgments (14%) have a no-violation target. Report balanced accuracy and class recalls.

## Exclusions

Of 356 judgments, 259 were eligible. Exclusions:

| Reason | Judgments |
| --- | ---: |
| HUDOC document body returned HTTP 204 | 61 |
| Factual appendix could not be resolved under the v1.0 column rules | 19 |
| No single-respondent holding resolved | 10 |
| No specific, unambiguous issue | 4 |
| Source review: insufficient facts | 2 |
| Application number shared with v1.0 | 1 |

The cause of the 204 responses is unknown and they may not be random, so the
cohort does not represent every judgment published in the window. One of the 129
generated summaries failed all attempts; the substitution rule covers such cases.

## Limits and remaining work

Targets were verified automatically against official HUDOC holdings. Leakage review
was by model plus a deterministic phrase scan; no person read every source or summary.
The v1.0 anchor cohort is part of the evaluation step and has not been selected.
Do not claim post-v1.0 results until the evaluation artifacts exist.
