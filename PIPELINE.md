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

For example, build a refreshed source file using the full verdict-removal pipeline:

```bash
python scripts/hudoc_live_refresh.py \
  --hf-dataset overthelex/echr-verdict-free \
  --output data/processed/echr_live_new.json \
  --full-pipeline
```

`--since-override`, `--country` and `--workers` control the refresh. The full
pipeline includes model verification; its credentials and dependencies are
listed in the script and `requirements.txt`.

## Construct and freeze an evaluation release

1. Normalize respondent names, decision dates and provision identifiers with
   `clean_respondent_names.py`, `backfill_decision_dates.py` and
   `backfill_article_full.py` under `scripts/`.
2. Select a candidate cohort. `scripts/build_unified_set.py` supports
   `--min-year`, `--max-year`, `--cap`, `--target`, `--include-ukraine` and
   `--out`. Its source is the local `echr_livehrb_static_2k.json` corpus.
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

## Earlier source-set builders

`build_livehrb_static.py`, `build_temporal_split.py` and
`build_cutoff_partitions.py` remain available under `scripts/` for the earlier
source-set designs. Their 2k splits and model-cutoff configuration describe those
designs. Current manuscript results use the frozen cohort and experiment-specific
references above.
