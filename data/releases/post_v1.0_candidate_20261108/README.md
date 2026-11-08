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
| `core_50_cases.json`, `core_50_summaries.json`, `core_50_target_audit.json`, `core_50_evaluation_dataset.json` | The starting cohort as a self-contained cohort, id `echr-post-v1.0-candidate-20261108-core50` |
| `release_manifest.json` | Retrieval date, HUDOC query, seed, selection rule, hashes |
| `target_audit.json` | Official HUDOC holding behind each target |
| `operative_check.json` | Each target compared with the judgment's operative part |
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

## Replacements after the first freeze

Five targets were found unsuitable, before any target-model call: four by the
operative-part check and one by a check of the model inputs.
Each was replaced by the next-ranked judgment with an accepted summary in the same
stratum, and in the same month for violation targets. `core_50.json` did not change.
Reasons are in `release_manifest.json`.

| Removed | Reason | Added |
| --- | --- | --- |
| 001-251017, 001-252645 | The finding is only in the excluded other-complaints column, so the input has no facts on length | 001-251013, 001-252929 |
| 001-252653 | The finding on the presumption of innocence is only in the excluded other-complaints column, so the input has no facts on it | 001-252899 |
| 001-250744, 001-252642 | The same fair-hearing wording also covers a violation in the judgment (first); the outcome differs by applicant and the question names none (second) | 001-250619, 001-252628 |

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

The 204 responses are not random by construction and their cause is unknown, so
the cohort does not represent every judgment published in the window. One summary
failed all attempts and was replaced under the substitution rule.

## Running the evaluation

`validate_eval_dataset.py` compares this cohort with its own manifest only. The
experiment runners also require the run cases to match the active cohort, whose paths
are fixed in `experiments/input_gate.py`, so `--cases` alone is rejected with
`Target is not in the active cohort`. Run from a separate worktree with this cohort
installed as the active one, and do not commit the three replaced files:

```bash
git fetch origin
git worktree add ../lhrb-post-v1.0-eval origin/data/post-v1.0-candidate-20261108
cd ../lhrb-post-v1.0-eval
D=data/releases/post_v1.0_candidate_20261108
cp $D/core_50_cases.json data/processed/echr_unified.json
cp $D/core_50_summaries.json data/processed/summaries_dsv41flash.json
cp $D/core_50_evaluation_dataset.json configs/evaluation_dataset.json
python scripts/validate_eval_dataset.py --require-complete
python scripts/verify_model_input_payloads.py
```

For all 100 targets, copy `cases.json`, `summaries.json` and `evaluation_dataset.json`
instead. The v1.0 anchor needs the same treatment with its own frozen subset, in its
own worktree, because the gate also rejects a partial v1.0 cohort.

Full record and summary, for the two models named in EmoP-5:

```bash
for m in openai/gpt-5.6-sol anthropic/claude-opus-4.6; do
  python experiments/run_perturbation_fullcase.py \
    --cases data/processed/echr_unified.json \
    --summaries data/processed/summaries_dsv41flash.json \
    --model "$m" --base-url https://openrouter.ai/api/v1 \
    --api-key-env OPENROUTER_API_KEY --samples 10 --workers 20 --rq all \
    --output-dir data/experiments/post_v1_core50/fullcase
done
```

Three-turn comparison:

```bash
python experiments/syco_run.py \
  --cases data/processed/echr_unified.json \
  --summaries data/processed/summaries_dsv41flash.json \
  --out data/experiments/post_v1_core50/syco \
  --targets openai/gpt-5.6-sol anthropic/claude-opus-4.6 --turns 3
```

`syco_run.py` runs all eleven conditions and has no option to restrict them. EmoP-5
needs only the no-cue and researcher comparison (`baseline_high`, `authority_researcher`).
Restrict `condition_grid()` in the worktree or budget for the full grid.

## Limits and remaining work

Every outcome was compared with the operative part of the published judgment
(`operative_check.json`). 93 targets match it uniformly. Six judgments reach different
outcomes under the same provision and were read individually; each target matches its
sub-conclusion. In one the operative part states the provisions in reverse order
(Article 3 taken in conjunction with Article 14). The issue wording of the uniform
matches comes from the official HUDOC holding and was not read separately.
Leakage review was by model plus a deterministic phrase scan; no person read every
source or summary. Rainbow Mission Foundation (001-251024, in the core) is kept, but
only the reference to Article 10 distinguishes its target from a violation under the
same provision. All 100 inputs and summaries were searched for facts on the topic of the
target, and the complaint wording of the 58 Committee inputs was read. This shows that
the topic is present, not that the facts suffice for a ruling. Some Committee inputs are
very short, for example one sentence of complaint and the detention dates.
The v1.0 anchor cohort is part of the evaluation step and has not been selected.
Do not claim post-v1.0 results until the evaluation artifacts exist.
