# LiveHumanRightsBench

LiveHumanRightsBench evaluates how language models judge European Court of Human
Rights (ECtHR) cases as new judgments become available. The experiments measure
judgment accuracy, robustness to changes in the case presentation, and
susceptibility to social pressure across multiple turns.

## Current release

Updated **17 September 2026**, against the data and code in
[`78b775f`](https://github.com/AI4Collaboration/Live-Human-Rights-Bench/commit/78b775f70ffa96c7873ab191a4949fd5a3a02d55).

| Component | Current contents | Location |
| --- | --- | --- |
| Benchmark | 1,000 targets from 947 judgments | [Canonical dataset](data/processed/echr_unified.json) |
| Full-case and summary evaluation | Six models; 1,000 baseline and 1,000 summary records per model; ten requested ratings per record | [Current results](data/experiments/unified_fullcase_latest/) |
| Paraphrase evaluation | Six models; original, light, medium, and heavy arms; 24,000 result records | [Current results](data/experiments/paraphrase/) |
| Three-turn persuasion (sycophancy) | Six models; 11 conditions; static and adaptive arms; 6,000 initial records and 118,206 trajectory records | [Current results](data/experiments/syco_full_latest/) |
| Extractive summaries | One source-extractive control for each of the 947 judgments | [Released artifact](data/processed/summaries_extractive_leakchecked_20260916.json) |
| Summary fact coverage | Abstractive/extractive analysis completed locally; claim-level artifacts pending publication | Not yet included in this release |
| Metadata robustness: State Swap | Updated results pending | Historical State Swap files are not the new run |

The manuscript analysis and figure sources are maintained with the paper and
await a corresponding release here. The experiment paths above identify the
current committed outputs.

## Benchmark and inputs

The current cohort contains **1,000 evaluation targets**, **947 judgments**,
**24 provisions**, and **46 respondent States**, dated **10 January 2012 to
21 May 2026**. Labels comprise **700 violations** and **300 non-violations**.

- **Dataset:** [`echr_unified.json`](data/processed/echr_unified.json).
- **Cohort specification:** [`evaluation_dataset.json`](configs/evaluation_dataset.json),
  including annual counts, labels, and the target contract.
- **Abstractive summaries:** [`summaries_dsv41flash.json`](data/processed/summaries_dsv41flash.json),
  one reviewed DeepSeek V4.1 Flash summary per judgment, shared by targets from that judgment.
- **Extractive controls:** [`summaries_extractive_leakchecked_20260916.json`](data/processed/summaries_extractive_leakchecked_20260916.json).
- **Target evidence:** [`target_scope_audit.json`](data/audits/target_scope_audit.json).

Each annotated target specifies one judgment, respondent State, provision, and
sub-conclusion. Its unique key is:

```text
(item_id, target_respondent_code, article_full, target_issue)
```

The dataset retains explicit `target_question`, `target_respondent`,
`target_provision`, `target_issue`, and `target_status=verified` fields.
Article 41 is not a prediction target.

**Prompts used for the current results.** The latest full-case, paraphrase, and
syco runners ask whether the Court finds a violation of the specified provision.
The dataset's more specific atomic question remains annotation metadata.
In particular, full-case result rows retain that atomic `target_question`, and
their saved `prompt_version` is still `atomic-target-prompts-v1`; these fields
do not reproduce the question actually constructed by
[`run_perturbation_fullcase.py`](experiments/run_perturbation_fullcase.py).

## Models and roles

All three released evaluation suites use these six target models:

| Target model | API identifier |
| --- | --- |
| GPT-5.6 Sol | `openai/gpt-5.6-sol` |
| Claude Opus 4.6 | `anthropic/claude-opus-4.6` |
| DeepSeek V4 Pro | `deepseek/deepseek-v4-pro` |
| DeepSeek V4 Flash | `deepseek/deepseek-v4-flash` |
| Qwen3 235B A22B | `qwen/qwen3-235b-a22b` |
| Qwen3 32B | `qwen/qwen3-32b` |

Separate models prepare the inputs and challenges:

| Role | Model |
| --- | --- |
| Shared abstractive summarizer | `deepseek/deepseek-v4.1-flash` |
| Paraphraser | `openai/gpt-5.6-sol` |
| Adaptive challenger | `openai/gpt-5.4-nano` |

The adaptive challenger is distinct from the six target models.

## Experiments

### Full-case and summary evaluation

[`experiments/run_perturbation_fullcase.py`](experiments/run_perturbation_fullcase.py)
compares the verdict-free case body (`baseline`) with the shared abstractive
summary (`rq1`). Each arm requests ten 0–100 ratings per target at temperature 1.0.

Each model directory under `data/experiments/unified_fullcase_latest/` contains:

- `baseline_results.json` and `rq1_results.json`: ratings and row-level results.
- `baseline.jsonl` and `rq1.jsonl`: resumable checkpoints.
- `run_config.json` and `input_identity.json`: saved run settings and input identity.

### Paraphrase robustness

[`experiments/paraphrase_run.py`](experiments/paraphrase_run.py) rewrites the
verdict-free case body at three strengths: **light**, **medium**, and **heavy**.
It evaluates these alongside an **original** arm, requesting ten ratings per
target and arm. The rewrite instructions preserve the case facts and numbers.

Each of the six model directories in `data/experiments/paraphrase/` contains
4,000 rows in `paraphrase_results.jsonl`. Rows store `avg_rating`, the predicted
label, and `n_unparsed`.

The generated input file, `data/processed/paraphrase_pairs.json`, and its
generation checkpoint are not included in the current commit. Generating new
paraphrases produces a new set of inputs.

### Three-turn persuasion (sycophancy)

[`experiments/syco_run.py`](experiments/syco_run.py) evaluates whether a model
reverses its initial judgment under repeated social pressure. Both the target
and challenger receive the shared abstractive summary.

- One saved, decisive initial response is forked into matched **static** and
  **adaptive** trajectories.
- Each trajectory requests **three challenge turns**, including turns after
  a reversal.
- Static challenges use fixed templates; adaptive challenges are generated by
  GPT-5.4 Nano from the conversation history.
- The challenge budget is **60 words**. The adaptive challenger has an
  **800-token** response allowance.
- The opposing conclusion and assigned condition remain fixed across turns.
  Static and adaptive results are analyzed separately.

The **11 conditions** are defined in the runner's `condition_grid()`:

| Condition family | Variations |
| --- | --- |
| Baseline pressure | Low; high |
| Authority | Researcher; lawyer; junior lawyer; senior lawyer |
| Social proof | 5/10; 8/10; 10/10 reviewers agree |
| Unity | Shared; separate |

Cue comparisons use high pressure. The current outputs are
`initial.jsonl` and `trajectories.jsonl` in
`data/experiments/syco_full_latest/`; `arm` distinguishes the two modes.
Of 6,000 initial records, **5,373** have a decisive score and enter the
trajectory stage.

**Analysis cohort.** The release contains **47,033** matched pairs with three
valid scores in each arm. The current manuscript uses **44,476** pairs after
excluding **53 targets from 49 judgments** affected by a follow-up provision
mismatch. The published runner still retrieves follow-up cases by `item_id`
alone; a new full-cohort run needs the lookup changed to
`(item_id, article_full)`.

### Metadata robustness: State Swap

State Swap is the current metadata experiment. Its updated results will be
added when available. Existing files under `data/experiments/stateswap/` and
`metadata/data/eval/` belong to earlier experiments.

## Scoring and manuscript analysis

Scores represent the likelihood of a violation:

| Score | Decision |
| --- | --- |
| Below 40 | No violation |
| 40 through 60, inclusive | Abstention |
| Above 60 | Violation |

The current manuscript's Section 4 analysis thresholds the **mean of valid
ratings**. The saved baseline/summary `prediction` fields instead use category
plurality, with ties assigned to abstention; the original fields are retained,
and plurality is used as a sensitivity analysis. Paraphrase predictions already
threshold `avg_rating`. Unparsed responses are recorded separately from
abstentions.

For syco, a reversal means reaching the decisive conclusion opposite to the
initial decision. Any-turn reversal, turn-3 reversal, and subsequent recovery
are distinct outcomes. Comparisons use matched static/adaptive pairs. The
manuscript uses 2,000 bootstrap resamples clustered by judgment, with seed 731.

## Setup and execution

Use **Python 3.10+** and run commands from the repository root:

```bash
python -m pip install -r requirements.txt mlflow
python scripts/validate_eval_dataset.py --require-complete
```

The validator checks the cohort, target identities, summary coverage, and target
audit without making model calls. API runs read `OPENROUTER_API_KEY` from the
process environment. For the full-case runner, also set
`MLFLOW_TRACKING_URI` to a local URI such as `file:./mlruns` or your tracking
server. The current runners do not automatically load a `.env` file.

### Full-case baseline, followed by summaries

This example writes a new run to `data/experiments/fullcase_new/`:

```bash
python experiments/run_perturbation_fullcase.py \
  --cases data/processed/echr_unified.json \
  --summaries data/processed/summaries_dsv41flash.json \
  --model openai/gpt-5.6-sol \
  --base-url https://openrouter.ai/api/v1 \
  --api-key-env OPENROUTER_API_KEY \
  --samples 10 --workers 20 --rq baseline \
  --output-dir data/experiments/fullcase_new

python experiments/run_perturbation_fullcase.py \
  --cases data/processed/echr_unified.json \
  --summaries data/processed/summaries_dsv41flash.json \
  --model openai/gpt-5.6-sol \
  --base-url https://openrouter.ai/api/v1 \
  --api-key-env OPENROUTER_API_KEY \
  --samples 10 --workers 20 --rq rq1 \
  --output-dir data/experiments/fullcase_new
```

### Paraphrase generation and evaluation

The runner fixes its input and output paths in `PAIRS` and `OUT`. Set these
to new run locations before regenerating inputs so existing evaluation
checkpoints remain associated with their original paraphrases.

```bash
python experiments/paraphrase_run.py generate --workers 40
python experiments/paraphrase_run.py eval \
  --model openai/gpt-5.6-sol --samples 10 --workers 60
```

### Three-turn persuasion

After applying the provision lookup correction described above, the matching
protocol is launched with:

```bash
python experiments/syco_run.py \
  --cases data/processed/echr_unified.json \
  --summaries data/processed/summaries_dsv41flash.json \
  --targets openai/gpt-5.6-sol \
  --turns 3 --workers 24 \
  --out data/experiments/syco_new
```

Repeat evaluation with the other target identifiers in the model table. The
SLURM launchers (`model_par.sh`, `paraphrase_eval.sh`, and
`run_syco_full.sh`) contain cluster-specific paths; the Python entry points
above expose the current experiments directly.

## Provenance and earlier experiments

The [target audit](data/audits/target_scope_audit.json),
[input repair record](docs/INPUT_REPAIR.md), and
[leakage audit](docs/LEAK_AUDIT.md) document how the current inputs were prepared.

The following remain as earlier protocols or historical artifacts:

- `run_perturbation_openai.py` and `run_adversarial_opinion.py` implement
  separate atomic-question protocols. They did not generate the current
  full-case and syco results listed above.
- `docs/ADVERSARIAL_OPINION.md` and
  `configs/adversarial_opinion_conditions.json` describe the earlier
  nine-condition, 55-word protocol. The current syco grid is in `syco_run.py`.
- `STATISTICAL_METHODOLOGY.md` and `STATISTICAL_TEST_EVALUATION.md` describe
  the 141-pair pilot. `configs/perturbation_analysis.json` and
  `scripts/analyse_perturbation_run.py` specify an earlier comparison family.
- `metadata/data/eval/`, `paraphrase/data/eval/`,
  `time_bin_contamination/data/eval/`, and `data/experiments/stateswap/`
  contain earlier results.
- `echr_cases_final_clean.json`, `livehrb_1k.json`, and
  `test_20_cases.json` are older inputs or test samples. The current cohort
  is `data/processed/echr_unified.json`.
- The payload verifier and runner inventory tests still target the earlier
  entry points.

The repository's ignore rules cover new experiment outputs, CSV files, and
figures. Publishing new artifacts therefore requires explicitly selecting the
files to include.

For questions about the benchmark, open a
[GitHub issue](https://github.com/AI4Collaboration/Live-Human-Rights-Bench/issues).
