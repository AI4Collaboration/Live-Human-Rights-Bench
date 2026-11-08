# LiveHumanRightsBench

LiveHumanRightsBench evaluates the reliability of model judgments using European
Court of Human Rights (ECtHR) cases. Its three components are a **Live Benchmark**,
**Systematic Perturbation** and **Adversarial Opinion**.

## Rebuttal: completed analyses and the remaining task

**8 November 2026.** Responses to all three reviews and their evidence are in
the [rebuttal package](docs/rebuttal/README.md). The focused API collection is
complete and cost **$23.33** against a $50 ceiling. No additional paid runs are
scheduled here. The earlier full-cohort experiment queue is superseded.

| Reviewer concern | Evidence now available |
| --- | --- |
| Disagreement versus instruction following | Opinion-only challenges reverse 13/50 Opus-4.6 judgments and 12/46 5.6-Sol judgments, versus 1/50 and 1/46 under neutral reassessment. Challenges containing a replacement demand produce higher reversal rates. |
| Evaluation awareness versus role identity | With AI researcher identity fixed, evaluation wording lowers 5.6-Sol reversal from 30/49 to 19/49. Opus is already at 1/50 under neutral framing; V4-Flash remains highly reversible. |
| Variability across conversations | Three independent continuations per reference condition preserve the large researcher-cue effect. Complete comparisons use 48 Opus cases and 49 Sol cases, with case-level variability reported. |
| Paraphrase fact preservation | An independent verifier and a filter defined without model judgments retain 540 targets with every sampled fact supported in all three rewrites. Judgment changes remain 4.8–15.4% across the five primary models and strengths. |
| Release consistency | All three v1.0 input hashes match the release manifest. An offline chronological reconstruction preserves the existing release exactly. |

[Reviewer responses](docs/rebuttal/RESPONSES.md) ·
[Point-by-point tracker](docs/rebuttal/review_tracker.csv) ·
[Results and denominators](analysis/rebuttal_20261107/REPORT.md) ·
[Frozen protocol](docs/rebuttal/EXPERIMENTS.md) ·
[Raw requests and responses](data/experiments/rebuttal_20261107/)

**Task to assign separately:** collect and evaluate genuinely new judgments
after the v1.0 endpoint of 21 May 2026. The
[handoff](docs/rebuttal/DELEGATED_TASKS.md) specifies source review, release
artifacts and a focused evaluation with a contemporaneous v1.0 anchor. The
current chronological reconstruction is an existing-data check, not evidence
that the findings generalize to a new release.

## Current release

**v1.0 contains 1,000 targets from 947 judgments**, dated 10 January 2012 to
21 May 2026, covering 24 provisions and 46 respondent countries. Labels comprise
700 violations and 300 non-violations.

- [Canonical dataset](data/processed/echr_unified.json) and
  [release manifest](configs/releases/v1.0.json).
- [Data and result inventory](data/README.md), including earlier models and
  the separate control and reasoning runs.
- [Analysis directory](analysis/README.md), with source tables and reproduction
  commands for each result.
- [Construction pipeline](PIPELINE.md), [task contract](DATA_SPLITS.md) and
  [release policy](docs/BENCHMARK_RELEASES.md).

## Latest CoT analysis

The [full-explanation analysis](analysis/reasoning_traces/full_text/README.md)
compares complete recorded explanations under no cue, lawyer and AI safety
researcher. First-turn comparisons use the same 734 Opus-4.6 instances and
946 V4-Flash instances across all three cues. Missing explanations are reported
separately; there is no word-length cutoff.

The report includes length distributions, paired changes, evaluation-language
frequency per explanation and per thousand words, and three-turn comparisons.
Researcher-cue evaluation-language density is 2.0 times the no-cue density for
Opus-4.6 and 5.1 times for V4-Flash. These are measurements of written explanations.
The [CoT index](analysis/reasoning_traces/README.md) distinguishes these results
from whole-cohort reversal rates and supplementary examples.

```bash
python analysis/analyze_reasoning_full_text.py
```

This reads the frozen Git source records and makes no model calls.

## Benchmark and inputs

The canonical target key is
`(item_id, target_respondent_code, article_full, target_issue)`.
Each target identifies a judgment, respondent country, provision and issue.
The released runners ask a provision-level question; see
[prompt identity](docs/EXPERIMENTS.md#prompt-identity) for the distinction from
annotation fields and historical prompt tags.

All summary-based experiments share the selected
[abstractive summaries](data/processed/summaries_dsv41flash.json).
[Extractive controls](data/processed/summaries_extractive_leakchecked_20260916.json)
and [input-review evidence](data/audits/README.md) are also released.
The [source register](docs/DATA_SOURCE_STATUS.md) identifies deprecated sources
and inputs still awaiting publication.

## Models and roles

Current primary analyses compare five target models:

| Target model | API identifier |
| --- | --- |
| GPT-5.6 Sol | `openai/gpt-5.6-sol` |
| Claude Opus 4.6 | `anthropic/claude-opus-4.6` |
| DeepSeek V4 Pro | `deepseek/deepseek-v4-pro` |
| DeepSeek V4 Flash | `deepseek/deepseek-v4-flash` |
| Qwen3 32B | `qwen/qwen3-32b` |

GPT-4o mini and GPT-4.1 mini add baseline and perturbation controls. This makes
seven models for those comparisons; the main three-turn adversarial-opinion
analysis has five. Qwen3-235B outputs remain in the historical checkpoints but
are excluded from current primary analyses. The separate reasoning runs cover
Opus-4.6 and V4-Flash.

The shared summarizer is `deepseek/deepseek-v4.1-flash`, the paraphraser is
`openai/gpt-5.6-sol`, and the adaptive challenger is `openai/gpt-5.4-nano`.
[Verified model cutoffs](configs/model_knowledge_cutoffs.json) support the
[earlier-model temporal analysis](analysis/model_time_windows/REPORT.md).

## Experiments

| Experiment | Protocol | Analysis |
| --- | --- | --- |
| Baseline and Summarization | [Inputs, prompts and execution](docs/EXPERIMENTS.md#full-case-and-summary-evaluation) | [Accuracy and time windows](analysis/model_time_windows/REPORT.md) |
| Paraphrasing | [Three rewrite strengths](docs/EXPERIMENTS.md#paraphrase-robustness) | [Changes and threshold sensitivity](analysis/threshold_sensitivity/REPORT.md) |
| Country Swap | [Transformation and validity check](docs/STATESWAP.md) | [Context-screened comparisons](analysis/stateswap_context/REPORT.md) |
| Adversarial Opinion | [Conditions and conversations](docs/ADVERSARIAL_OPINION.md) | [Cue effects and correctness](analysis/reliability_controls/REPORT.md) |
| Additional controls | [Released conditions](analysis/september_controls/REPORT.md) | [Control contrasts](analysis/september_controls/REPORT.md) |
| CoT | [Full-explanation method](analysis/reasoning_traces/full_text/README.md) | [Results and evidence](analysis/reasoning_traces/README.md) |

[All analyses](analysis/README.md) include failure timing, score variability,
evaluator exclusions, human validation and the worked case example.
Historical `syco_*` and `stateswap_*` filenames remain stable for reproducibility.

## Scoring and manuscript analysis

Scores below 40 predict no violation; scores above 60 predict violation.
Scores from 40 through 60 are abstentions. Fixed-input analyses threshold the
mean of valid ratings. A strict reversal reaches the decisive verdict opposite
to the initial verdict; abstention is reported separately.

Accuracy, judgment change, reversal and text-frequency rates use different
eligible cohorts. Exact denominators and bootstrap settings are recorded in
each analysis report and the [statistical methodology](STATISTICAL_METHODOLOGY.md).

## Setup and execution

Use Python 3.10+ from the repository root:

```bash
python -m pip install -r requirements.txt
python scripts/validate_eval_dataset.py --require-complete
```

For offline tests, install `requirements-dev.txt` and run `python -m pytest -q`.
The validator makes no model calls. [Execution commands](docs/EXPERIMENTS.md#setup-and-execution)
cover new runs, environment settings and offline Country Swap preflight.
Each new run must use its own output directory and retain input identities.

## Input provenance and deprecated sources

The six legacy Hugging Face releases are **deprecated as evaluation inputs**.
Use the GitHub inputs identified in the [source register](docs/DATA_SOURCE_STATUS.md)
and its [machine-readable inventory](configs/data_source_status.json).
[Pending input artifacts](docs/DATA_SOURCE_STATUS.md#pending-inputs) are listed explicitly.

## AI assistance

Coding agents assisted with coding and refactoring. We reviewed the code and
checked its outputs against the saved experiment results. The paper provides
the full AI-use disclosure.
