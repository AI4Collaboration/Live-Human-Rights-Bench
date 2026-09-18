# Live HUDOC ingestion and benchmark construction

LiveHumanRightsBench turns public ECtHR judgments into versioned evaluation sets.
Researchers can configure the sampling window and sample size, then apply the same
input transformations and conversational challenges to each frozen release.
The paper's 1,000-target sample is one use of this pipeline.

## Refresh the source corpus

`scripts/hudoc_live_refresh.py` detects the latest decision date in an existing
local or Hugging Face corpus, fetches newer HUDOC judgments, processes their
text, and appends the new records. Publication to Hugging Face is optional.

```text
scripts/hudoc_live_refresh.py
  -> scripts/hudoc_scraper.py
  -> scripts/verdict_leakage_removal.py
  -> scripts/conclusion_scrub.py
  -> updated source corpus
```

For example, refresh an explicitly selected local candidate corpus:

```bash
python scripts/hudoc_live_refresh.py \
  --dataset path/to/pinned_candidate_corpus.json \
  --output data/processed/echr_live_new.json \
  --full-pipeline
```

`--since-override`, `--country` and `--workers` control the refresh. The full
pipeline includes model verification; its credentials and dependencies are
listed in the script and `requirements.txt`.

The legacy Hugging Face pools are **deprecated as evaluation inputs**; their
versions and historical roles are in [DATA_SOURCE_STATUS.md](docs/DATA_SOURCE_STATUS.md).
They may supply candidates for a new release. The refresh processes newly
fetched judgments and retains existing rows, so `--full-pipeline` does not repair
an older corpus retroactively. Review the complete proposed release before use.

## Construct and freeze an evaluation release

1. Normalize respondent names, decision dates and provision identifiers with
   `clean_respondent_names.py`, `backfill_decision_dates.py` and
   `backfill_article_full.py` under `scripts/`.
2. Select a candidate cohort. `scripts/build_unified_set.py` supports
   `--min-year`, `--max-year`, `--cap`, `--target`, `--include-ukraine` and
   `--out`. This historical sampler reads the local `echr_livehrb_static_2k.json`
   corpus. Write candidates to a separate `--out` path; sampling the deprecated
   static source does not reconstruct the current reviewed release.
3. Resolve each target's respondent, provision and sub-conclusion against the
   public judgment. Record the target audit and review retained case text.
4. Freeze the approved cohort, summary selection and counts in
   `configs/evaluation_dataset.json`, then validate the release.
5. Save evaluations in new output directories with their input and prompt
   identities. A source-corpus refresh creates candidates for a new release.

The candidate sampler precedes atomic target resolution and input review. The
current approved release is recorded in [DATA_SPLITS.md](DATA_SPLITS.md), with
preparation evidence in [docs/INPUT_REPAIR.md](docs/INPUT_REPAIR.md) and
`data/audits/target_scope_audit.json`.

```bash
python scripts/validate_eval_dataset.py --require-complete
```

The validation command checks the existing frozen release without calling models.

## Evaluate the frozen release

| Evaluation | Current entry point | Reference |
| --- | --- | --- |
| Full record and shared summary | `experiments/run_perturbation_fullcase.py` | Matched full-record arm |
| Case-body paraphrases | `experiments/paraphrase_run.py` | Original arm under the same prompt |
| Three-turn persuasion | `experiments/syco_run.py` | Shared initial response |
| Extractive control and fact retention | `scripts/build_extractive.py`, `scripts/build_atomic_coverage.py` | Identical source claims across summary variants |

[README.md](README.md) provides model identifiers, execution commands and the
current run inventory. [STATISTICAL_METHODOLOGY.md](STATISTICAL_METHODOLOGY.md)
defines scoring and comparisons. State Swap supplies the respondent-identity
intervention; its updated result is the remaining manuscript Results entry.

## Deprecated sources

Use the [source-status register](docs/DATA_SOURCE_STATUS.md) to check any source
before evaluation. The six superseded Hub releases are deprecated as evaluation
inputs. Their importers do not reconstruct the current reviewed release.
