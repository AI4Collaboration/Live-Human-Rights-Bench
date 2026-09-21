# LiveHumanRightsBench

## Next API experiments

**Plan audited 21 September 2026 against the published results and runners.
The follow-up API experiments below remain pending.**

**New results incorporated:** the [Türkiye State Swap follow-up](analysis/stateswap_turkey/REPORT.md)
is complete for GPT-4o mini, GPT-4.1 mini and GPT-5.6-sol: 12,000 records and
120,000 parsed ratings. It adds a destination comparison; the UK/France control
with an explicitly fixed Convention framework below remains conditional.

Prioritize the role-cue finding and conversational sampling variability. Use
Claude Opus 4.6 and GPT-5.6-sol, exact saved initial responses, and a locked
100-case subset of the shared 349-case cohort. Existing conditions below are
concurrent replication references, not new role additions.

| Priority | Experiment | Why it matters | New generations |
| --- | --- | --- | ---: |
| First | AI researcher + neutral reassessment, with concurrent no-cue and AI safety researcher references | Separate the `safety` wording effect from ordinary reconsideration and serving-time changes | 2,400 target responses |
| First | Repeat the two reference conditions on 50 of those cases, five static trajectories in total | Measure within-case variability of the headline role contrast | +2,400 target responses; first trajectories reused |
| Recommended next | Low-temperature static comparison on the same 50 cases, no cue and AI safety researcher, three trajectories | Test whether the role contrast and harmful revisions persist with less sampling randomness | +1,800 target responses |
| Conditional next | Repeat the same two conditions in adaptive mode on the same 50 cases, five trajectories | Check whether the role contrast survives variation in the evolving challenger and target | +3,000 target responses and 3,000 challenger generations |
| Retained role extensions | Generic researcher; judge | Broader research identity and legal authority | +1,200 new-cue responses; +600 for a concurrent lawyer reference |
| Separate identity extension | Same / different nationality as respondent | Nationality alignment without professional-role cues | +1,200 target responses |
| Optional role extensions | Human rights researcher; ordinary person; AI systems researcher | Domain relevance, non-expert identity, or equal-word-count role wording | +600 target responses per cue |
| Conditional mechanism test | Role by explicit evaluation framing | Test evaluation signaling if advancing a mechanism claim | 2,400 target responses for one trajectory in each of four cells |
| Conditional State Swap | United Kingdom / France destinations, with the Convention framework held fixed | Test respondent-country effects within the Convention, as requested in the Overleaf comments | 3,000 target responses |
| Optional generator control | Alternative summary or paraphrase generator | Test generalization across generators if the claim requires it | Specify a targeted subset and budget before scheduling |

**Recommended first batch: 4,800 target responses, no challenger calls.**
Adding the low-temperature comparison costs **6,600 target responses in total**,
with no challenger calls. Keep its serving window aligned with the reference
conditions; the comparison reuses saved initial judgments.
Adding adaptive replication brings the package to **7,800 target responses
plus 3,000 challenger generations**, or **9,600 plus 3,000** when the
low-temperature comparison is also included, before retries. References are collected
in the same serving window as the new conditions. Repetitions are averaged
within cases; they do not increase the independent case count.
The [merged protocol and exact budgets](docs/NEXT_EXPERIMENTS.md) specify
strata, cues, repeated-trajectory handling, runner changes and stopping rules.

Adding generic researcher, judge and both nationality cues to the static
package costs **7,800 target responses in total, with no challenger calls**,
including the concurrent lawyer reference. This total assumes all additions
share the references' serving window and excludes the optional experiments.

**Execution status:** the follow-up conditions are documented, but the current
runner still schedules the original fixed grid with one trajectory per branch.
Before execution, publish the locked 100-case and nested 50-case manifests,
add the new conditions and mode filters, distinguish repetitions in checkpoint
keys, and support replay of the saved initial replies and full message logging.
The existing launch command does not implement this follow-up plan.

**Already available:** AI safety researcher, lawyer, junior lawyer, senior
lawyer and no cue. Do not rerun their full cohorts as new role experiments.
Nationality and professional roles remain separate. The existing
[older-model nationality release](data/experiments/syco_nationality/) combines
nationality with a lawyer cue for one turn; it does not implement the planned
three-turn nationality-only comparison.

## Review follow-up without API calls

The [review assessment](docs/REVIEW_IMPROVEMENTS.md) distinguishes useful
additions, existing evidence and suggestions that do not fit the paper's claims.
The [offline review analyses](analysis/review_offline/REPORT.md) are complete:
paired Brier-score changes, five multiple-comparison families, cue contrasts,
and first-reversal/switch counts. Final conversational Brier error rises by
0.114-0.544 across all twelve model-mode combinations, with every adjusted
interval above zero. Five of six US shifts remain negative after correction;
all twelve comparisons with Russia and Ukraine retain that ordering. Prompt
examples, retry/failure behavior and source-review accounting have been clarified
in the manuscript, with relevant references verified against primary sources.
The model-call queue above remains pending.
Threshold sensitivity uses saved scores, not fresh model responses. Existing
source-review evidence and older-model time-window analyses address different
questions and remain separate.

The [failure mode analysis](analysis/failure_modes/REPORT.md) and all five
[fine-grained analyses](analysis/fine_grained_failures/REPORT.md) are complete:
initial score extremity, failure timing/recovery, error direction, cue effects
by initial correctness, and shared vulnerability across perturbations. They
require no new human annotation or model calls.

**Additional analyses completed without API calls:**

- **Summary score variance does not rise uniformly across models.** Within-target
  variance rises in two models and falls in four. The paired interval is positive
  for DeepSeek V4 Flash and negative for DeepSeek V4 Pro and both Qwen models.
  The [score variability analysis](analysis/summary_variability/REPORT.md) uses
  5,995 complete ten-score pairs and also reproduces the existing SD estimates.
- **The perturbation patterns persist after evaluator exclusions.** Removing
  both DeepSeek evaluators leaves summary accuracy 1.3-2.4 points lower in the
  four remaining models. Removing GPT-5.6-sol leaves paraphrase changes spanning
  -1.4 to +1.9 points. The [exclusion diagnostic](analysis/generator_exclusion/REPORT.md)
  keeps the generated inputs and 1,000-target cohort fixed for every model.
- **The main role and conversational results survive threshold changes.**
  Across five scoring rules, final conversational accuracy falls by 12.6-53.8
  points. The shared-case static researcher cue reduces strict reversals by
  86.2-90.8 points for Claude and 47.3 for GPT. Summary accuracy changes are
  more rule-sensitive (-5.7 to +0.4), while corrections and losses coexist.
  The [threshold report](analysis/threshold_sensitivity/REPORT.md) retains the
  original cohorts and separates rescored reversals from support for the
  challenger's fixed verdict.
- **Extreme scores still reverse to the opposite endpoint.** In the shared
  349-case comparison, static challenges without a cue turn 163/187 initially
  correct endpoint judgments wrong for Claude and 281/305 for GPT. Every one
  of these changes crosses from at most 10 to at least 90, or vice versa.
- **Errors appear early and rarely recover.** After the first static challenge,
  275/314 initially correct Claude answers and 281/314 GPT answers are already
  wrong. Of cases that become wrong at any turn, 1/288 and 7/297 respectively
  recover by the final turn. These are the shared no-cue cases.
- **Failure modes distinguish changing into an error from preserving one.**
  On the shared static Claude comparison, the researcher cue reduces
  correct-to-wrong changes from 287/314 to 1/314 while increasing final wrong
  answers among initially wrong cases from 4/35 to 35/35. The new analysis also
  identifies temporary errors and corrections that are later lost.
- **The researcher cue preserves correct and incorrect starting judgments.**
  On the shared 349-case static comparison, Claude retains 313/314 correct
  initial answers with the cue versus 27/314 without it, while correcting 0/35
  initial errors versus 31/35. GPT corrects 27/35 errors with the cue.
- **Summary-induced changes exceed same-input sampling variability in all six
  models.** At five ratings per compared prediction, the excess is 3.2–15.5
  percentage points; all six paired 95% intervals are above zero.

The [analysis report](analysis/reliability_controls/REPORT.md) includes both
challenge modes, all six models, matched denominators, CSV results and
reproduction instructions.
The [fine-grained report](analysis/fine_grained_failures/REPORT.md) additionally
provides five-role matched comparisons and 258 cross-perturbation overlap
estimates, with source checks and reproducible validation.

LiveHumanRightsBench evaluates how language models judge European Court of Human
Rights (ECtHR) cases as new judgments become available. The experiments measure
judgment accuracy, robustness to changes in the case presentation, and
susceptibility to social pressure across multiple turns.

## Current release

**LiveHumanRightsBench v1.0** is the current fixed release: 1,000 targets from
947 judgments, dated 10 January 2012 to 21 May 2026. The
[release manifest](configs/releases/v1.0.json) pins the input hashes.
The [pipeline and version policy](docs/BENCHMARK_RELEASES.md) support different
cohort sizes and later releases; new model results can evaluate the same v1.0.

**Earlier-model results reviewed 19 September 2026:** GPT-4o mini and GPT-4.1
mini add complete full-record, summary, paraphrase and State Swap outputs.
The [earlier-model time-window analysis](analysis/model_time_windows/REPORT.md)
uses their [verified knowledge dates](configs/model_knowledge_cutoffs.json),
with the six primary models evaluated on the same case splits as references.
Full-record balanced accuracy before/after its own cutoff is 55.3%/52.9% for
GPT-4o mini and 57.9%/62.1% for GPT-4.1 mini. Under summarization, their verdict
categories change on 17.0% and 22.6% of v1.0 targets. The report includes
uncertainty, annual results, reference-model comparisons and nationality coverage.

Published evaluation snapshot from **17 September 2026**,
[`78b775f`](https://github.com/AI4Collaboration/Live-Human-Rights-Bench/commit/78b775f70ffa96c7873ab191a4949fd5a3a02d55).
Summary-based State Swap results and country matching were updated in
[`4b231e1`](https://github.com/AI4Collaboration/Live-Human-Rights-Bench/commit/4b231e17e6dd65880e665c5fe298db3862ff5ade).

**Code and source status checked 21 September 2026:** the six legacy Hugging Face sources
are **deprecated as evaluation inputs**, including the old State Swap release.
Use the GitHub inputs below. See the
[source-status register](docs/DATA_SOURCE_STATUS.md) for exact Hub revisions,
deprecated local files, replacements and pending inputs; the same inventory is
available as [JSON](configs/data_source_status.json).

| Component | Current contents | Location |
| --- | --- | --- |
| Benchmark v1.0 | 1,000 targets from 947 judgments | [Canonical dataset](data/processed/echr_unified.json) |
| Full-case and summary evaluation | Six models; 1,000 baseline and 1,000 summary records per model; ten requested ratings per record | [Current results](data/experiments/unified_fullcase_latest/) |
| Paraphrase evaluation | Six models; original, light, medium, and heavy arms; 24,000 result records | [Current results](data/experiments/paraphrase/) |
| Three-turn adversarial opinion | Six models; 11 conditions; static and adaptive arms; 6,000 initial records and 118,206 trajectory records | [Current results](data/experiments/syco_full_latest/) |
| Extractive summaries | One source-extractive control for each of the 947 judgments | [Released artifact](data/processed/summaries_extractive_leakchecked_20260916.json) |
| Summary fact coverage | Abstractive/extractive analysis completed locally; claim-level artifacts pending publication | Not yet included in this release |
| Metadata robustness: State Swap | Six models; original, US, Russia and Ukraine summary arms; 24,000 result records | [Current results](data/experiments/stateswap_summary/) |
| Türkiye State Swap follow-up | GPT-4o mini, GPT-4.1 mini and GPT-5.6-sol; original, Türkiye, Russia and Ukraine arms; 12,000 records | [Results and offline audit](analysis/stateswap_turkey/REPORT.md) |
| Earlier-model extension | GPT-4o mini and GPT-4.1 mini; 20,000 full-record, summary, paraphrase and State Swap records, all with ten parsed ratings | [Inventory and analysis](analysis/model_time_windows/REPORT.md) |
| One-turn nationality extension | Both earlier models; 2,000 initial records; three-arm matched cohorts of 916 and 63 targets for GPT-4.1 mini and GPT-4o mini | [Coverage](analysis/model_time_windows/nationality_coverage.csv) |

Manuscript figure sources are maintained with the paper. The additional
[reliability analyses](analysis/reliability_controls/REPORT.md) are released
here alongside the committed experiment outputs.

## Benchmark and inputs

The **v1.0** cohort contains **1,000 evaluation targets**, **947 judgments**,
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
Published full-case rows retain the atomic `target_question` and the saved tag
`atomic-target-prompts-v1`. The executed question is constructed by
[`run_perturbation_fullcase.py`](experiments/run_perturbation_fullcase.py).
New runs use the corrected tag `provision-fullcase-prompts-v1` and a new output
directory; the question text is the same as in the published full-case run.

## Models and roles

The four primary evaluation suites use these six target models:

| Target model | API identifier |
| --- | --- |
| GPT-5.6 Sol | `openai/gpt-5.6-sol` |
| Claude Opus 4.6 | `anthropic/claude-opus-4.6` |
| DeepSeek V4 Pro | `deepseek/deepseek-v4-pro` |
| DeepSeek V4 Flash | `deepseek/deepseek-v4-flash` |
| Qwen3 235B A22B | `qwen/qwen3-235b-a22b` |
| Qwen3 32B | `qwen/qwen3-32b` |

Earlier-model controls add `openai/gpt-4o-mini` and `openai/gpt-4.1-mini` for
full-record, summary, paraphrase and State Swap evaluation. Their
[cutoff and temporal analysis](analysis/model_time_windows/REPORT.md) uses the
same v1.0 targets. The separate nationality extension uses a one-turn lawyer
cue. The six-model three-turn adversarial-opinion roster is unchanged.

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

### Three-turn adversarial opinion

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
| Authority | AI safety researcher; lawyer; junior lawyer; senior lawyer |
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
mismatch in the published checkpoints. The current runner joins follow-ups by
`(item_id, article_full)` and binds new checkpoints to the corrected protocol.
Use a new output directory for a new full-cohort run.

#### Planned role and nationality extensions

The [top-of-README experiment list](#next-api-experiments) and
[detailed plan](docs/NEXT_EXPERIMENTS.md) specify new professional-role cues and
the separate same/different nationality comparison. Existing AI safety
researcher and lawyer conditions are reference results, not pending full-cohort
runs. Start with the static pilots, then replicate selected contrasts with
adaptive challenges. The released runner currently contains the 11 conditions
above; new conditions must be added before execution.

### Metadata robustness: State Swap

[`experiments/stateswap_summary_run.py`](experiments/stateswap_summary_run.py)
applies country-name alias and demonym replacements to the shared abstractive
summary. It compares the original summary with US, Russia and Ukraine arms,
requesting ten ratings per target and arm. The six model directories contain
4,000 records each. Inputs are derived from the canonical cohort and summaries;
the previous Hub State Swap release remains **deprecated**.

The current transformation produces actual respondent substitutions with changed
text for 998 US, 966 Russia and 832 Ukraine targets. The common manuscript cohort
contains 800 targets from 757 judgments. All 24,000 published rows have a valid
score mean.

The [Türkiye follow-up](analysis/stateswap_turkey/REPORT.md) adds GPT-4o mini,
GPT-4.1 mini and GPT-5.6-sol on 785 common targets from 742 judgments. Russia
and Ukraine substitutions raise mean violation likelihood for the two earlier
models (+0.7 to +1.5 points), but lower it for GPT-5.6-sol (-1.0 to -1.4).
These directions persist after correction across nine model-destination effects.
All 120,000 requested ratings parse. This run has its own original arms and
cohort; its rows are not pooled with the original US comparison. See the
[State Swap protocol and input review](docs/STATESWAP.md).

## Scoring and manuscript analysis

The current [dataset contract](DATA_SPLITS.md),
[pipeline](PIPELINE.md), and
[statistical methodology](STATISTICAL_METHODOLOGY.md) describe the reported
release and comparisons.

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
python -m pip install -r requirements.txt
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

Choose explicit input and output paths for a new run. Missing variants and
failed rewrites are rejected rather than scored as unchanged originals.

```bash
python experiments/paraphrase_run.py generate \
  --pairs data/processed/paraphrase_pairs_new.json --workers 40
python experiments/paraphrase_run.py eval \
  --pairs data/processed/paraphrase_pairs_new.json \
  --out data/experiments/paraphrase_new \
  --model openai/gpt-5.6-sol --samples 10 --workers 60
```

Evaluation checkpoints bind the input texts, prompt and sample count. Changing
these settings requires a new output directory.

### Run three-turn adversarial opinion

The runner applies the case/provision lookup correction and uses a fresh,
versioned output directory:

```bash
python experiments/syco_run.py \
  --cases data/processed/echr_unified.json \
  --summaries data/processed/summaries_dsv41flash.json \
  --targets openai/gpt-5.6-sol \
  --turns 3 --workers 24 \
  --out data/experiments/syco_new
```

### Summary-based State Swap

```bash
python experiments/stateswap_summary_run.py \
  --model openai/gpt-5.6-sol --samples 10 --workers 60 \
  --out data/experiments/stateswap_summary_new
```

New runs record whether each arm changes the input, individual ratings and raw
responses. Checkpoint settings and canonical input identities are validated.

Repeat evaluation with the other target identifiers in the model table. For
syco, use a separate output directory per model or pass all target identifiers
to one invocation. The
SLURM launchers (`model_par.sh`, `paraphrase_eval.sh`, and
`run_syco_full.sh`) resolve the repository location and use the prepared Python
environment. Set the API key before launch and adjust scheduler resources for
your cluster. `scripts/run_roster.sh` runs the six current models through the
full-case and shared-summary arms with ten ratings per target.

## Input provenance and deprecated sources

The [target audit](data/audits/target_scope_audit.json) and
[input-review protocol](docs/INPUT_REPAIR.md) document the current inputs.

**Deprecated sources must not be used for current evaluations.** The
[source-status register](docs/DATA_SOURCE_STATUS.md) lists the six deprecated
Hub releases and their replacements. Superseded local inputs, old results,
alternative-corpus audits and archived trial programs have been removed.

The repository's ignore rules cover new experiment outputs, CSV files, and
figures. Publishing new artifacts therefore requires explicitly selecting the
files to include.

For questions about the benchmark, open a
[GitHub issue](https://github.com/AI4Collaboration/Live-Human-Rights-Bench/issues).
