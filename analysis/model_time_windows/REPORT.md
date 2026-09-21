# Earlier-model performance across the v1.0 time window

Source revision: `8c876a920864bfa3352927551161b16166572d35`. Checked on
19 September 2026. The new experiment extension was published in
[`f92bf0d`](https://github.com/AI4Collaboration/Live-Human-Rights-Bench/commit/f92bf0d357c98dac806c5c070e4816c445dc2a0b).
This analysis uses existing outputs, with no model calls or human annotation.

## Main findings

**Earlier models do not show a uniform decline after their knowledge cutoffs.** Full-record
balanced accuracy for GPT-4o mini is 55.3% before its own cutoff and 52.9%
after it. For GPT-4.1 mini, it is 57.9% before and 62.1% after. These are
different case cohorts, so the figures describe temporal performance rather
than an isolated effect of training exposure.

**Small aggregate changes conceal unstable individual judgments in the older
models too.** Summarization changes 17.0% of GPT-4o mini verdict categories and
22.6% of GPT-4.1 mini categories, while ordinary accuracy falls by only 0.7 and
1.4 percentage points. For GPT-4.1 mini, full-record no-violation recall of
34.3% falls to 12.7% with summaries, reducing balanced accuracy from 58.3% to
51.1%. On the common 159 recent targets, its balanced accuracy falls from
62.1% to 49.7% under summarization. Input representation remains central to
judgment reliability when earlier models are added.

**Strong reference models help interpret the older-model results on the same
cases.** On 159 targets after both earlier models' cutoffs, full-record balanced
accuracy is 50.4% for GPT-4o mini, 62.1% for GPT-4.1 mini, 57.8% for Claude Opus
4.6 and 69.9% for GPT-5.6 Sol. GPT-5.6 Sol has the highest point estimate across
all eight models. The reference-model comparisons use the older-model windows.

## Older-model cutoffs within v1.0

**LiveHumanRightsBench v1.0** contains 1,000 targets from 947 judgments dated
**10 January 2012 to 21 May 2026**. It is one fixed release of the refreshable
pipeline. The [release manifest](../../configs/releases/v1.0.json) pins the
input hashes, and [version policy](../../docs/BENCHMARK_RELEASES.md) separates
new model results from changes to the data.

| Earlier model | Documented knowledge cutoff | Targets at/before | Targets after | Full-record balanced accuracy: before | After |
| --- | --- | ---: | ---: | ---: | ---: |
| GPT-4o mini | [1 October 2023](https://developers.openai.com/api/docs/models/gpt-4o-mini) | 786 | 214 | 55.3% | 52.9% |
| GPT-4.1 mini | [1 June 2024](https://developers.openai.com/api/docs/models/gpt-4.1-mini) | 841 | 159 | 57.9% | 62.1% |

The GPT-4o mini post-cutoff cohort contains 167 violations and 47 no-violations;
the GPT-4.1 mini post-cutoff cohort contains 126 and 33. GPT-4o mini's ordinary
accuracy rises from 67.6% to 70.6% across its cutoff while balanced accuracy
falls. Reporting the outcome mix and both recalls makes this distinction clear.

**Analysis design.** The two earlier models define the cutoff partitions.
Claude Opus 4.6, GPT-5.6 Sol and the other four primary models supply reference
results on these identical targets. The
[source register](../../configs/model_knowledge_cutoffs.json) retains verified
provider dates for reference models as metadata. Their own cutoff dates do
not define additional analysis groups. This keeps the temporal question focused
on the older models and uses the full available older-model post-cutoff cohorts.

## Reference comparisons on identical targets

All values are percentages. The recent window is **2 June 2024 to 21 May 2026**:
159 targets from 148 judgments, with 126 violations and 33 no-violations.
Balanced accuracy averages the two outcome recalls with equal weights.

| Model | Full record, all: accuracy | Full record, all: balanced | Full record, recent: balanced | Summary, recent: balanced |
| --- | ---: | ---: | ---: | ---: |
| GPT-4o mini | 68.2 | 54.7 | 50.4 | 47.1 |
| GPT-4.1 mini | 67.9 | 58.3 | 62.1 | 49.7 |
| Claude Opus 4.6 | 74.7 | 62.9 | 57.8 | 57.6 |
| GPT-5.6 Sol | 83.5 | 75.5 | 69.9 | 70.9 |
| DeepSeek V4 Pro | 72.7 | 61.0 | 60.7 | 60.3 |
| DeepSeek V4 Flash | 70.1 | 51.8 | 52.2 | 50.6 |
| Qwen3 235B | 66.3 | 53.6 | 52.6 | 45.8 |
| Qwen3 32B | 69.1 | 54.3 | 52.8 | 51.2 |

On the recent full-record cohort, GPT-5.6 Sol exceeds GPT-4o mini by **19.5
points** in balanced accuracy (paired 95% interval [8.9, 29.4]) and GPT-4.1 mini
by **7.8 points** ([-2.8, 17.0]). GPT-4.1 mini exceeds GPT-4o mini by **11.7
points** ([2.3, 21.8]). Intervals resample judgments, keeping their targets and
all compared models together.

[Performance data](performance.csv) include both input forms, every decision
year, three five-year bands, shared older-model cutoff intervals and each
earlier model's own cutoff split. [Paired model differences](paired_model_differences.csv) keep
the cohort and input form fixed. The two earlier models are additional
controls; the existing three-turn adversarial-opinion suite still covers six models.

## Other results in the extension

Both earlier models have **1,000 full-record, 1,000 summary, 4,000 paraphrase and
4,000 State Swap records** each. All 20,000 records report ten parsed ratings
and valid means. The [inventory](result_inventory.csv) also covers the six
primary models and records missing means and partial ratings separately.

| Earlier model | Intervention | Category changes | Direct opposite-verdict reversals | Accuracy change, points |
| --- | --- | ---: | ---: | ---: |
| GPT-4o mini | Summary | 17.0% | 5.2% | -0.7 |
| GPT-4.1 mini | Summary | 22.6% | 8.8% | -1.4 |
| GPT-4o mini | Heavy paraphrase | 11.2% | 1.5% | +0.8 |
| GPT-4.1 mini | Heavy paraphrase | 14.5% | 3.7% | +0.1 |

Each row compares 1,000 targets with that experiment's own reference. Category
changes include transitions into or out of abstention. The
[transition counts](perturbation_changes.csv) include all three paraphrase
strengths, correctness directions and the shared recent cohort.

**Nationality cues leave GPT-4.1 mini highly susceptible to a single challenge.**
On 916 targets with a decisive initial judgment and valid outputs in all three
arms, reversals are 96.9% for a neutral lawyer, 95.2% for a lawyer sharing the
respondent's nationality and 94.9% for a lawyer with a different nationality.
For GPT-4o mini, only 63 of 955 initially decisive targets have valid outputs
in all three arms; their reversal rates are 61.9%, 57.1% and 38.1%. The
[coverage table](nationality_coverage.csv) separates missing outputs from
non-reversals. [Paired cue differences](nationality_contrasts.csv) and
[matched counts](nationality.csv) use each model's complete three-arm cohort.

## Protocol and source checks

- Full-record and summary runs have identical saved input identities and
  numerical settings across all eight models: ten requested ratings,
  temperature 1.0 and a 50,000-character case cap. The earlier-model run tag
  is `provision-fullcase-prompts-v1`; the six-model tag is
  `atomic-target-prompts-v1`. The [prompt documentation](../../README.md#benchmark-and-inputs)
  explains that the tag was corrected while the executed provision-level
  question was retained.
- This analysis thresholds the **mean of valid scores**, consistently with the
  manuscript. The saved full-record and summary `prediction` field uses
  category plurality. Both aggregation rules are checked against individual
  ratings; the saved output is retained intact.
- Missing means remain failures in the 1,000-target accuracy denominators.
  Paired perturbation changes use valid pairs and expose missing counts.
- Earlier-model State Swap configs declare `stateswap-summary-literal-v1`;
  the current six-model transformation uses country aliases. Input alignment
  is needed for an eight-model State Swap comparison. The inventory records
  completed outputs and their run configurations.
- Earlier-model nationality is a separate one-turn, lawyer-cue protocol with
  three requested initial and post-challenge ratings. Its continuation supplies
  the rounded initial score. Different nationality means French, except for
  French respondents, where it means German. It is separate from the planned
  three-turn nationality-only experiment and the released AI safety researcher
  condition.
- Provider cutoffs are temporal metadata. Establishing judgment-specific
  training exposure requires separate evidence.

## Presentation and reproduction

The temporal subsection should focus on **earlier-model performance before and
after the two documented cutoffs**. A compact table can show the two older
models, cutoff dates, cohort sizes and balanced accuracy before/after. A flat
matrix with chronological case groups can add Claude and GPT reference values
on the same groups. The reference models do not need their own cutoff panels.
Summary effects support the broader finding that small net accuracy changes
conceal unstable individual judgments and belong with the summarization result.

From the repository root:

```text
python analysis/analyze_model_time_windows.py
python analysis/validate_model_time_windows.py
```

The default source commit is pinned. The analysis uses NumPy and the Python
standard library, with 2,000 judgment-cluster bootstrap draws and seed 731.
[Cohort definitions](cohorts.csv), [input/output hashes](manifest.json) and
[independent validation](VALIDATION.json) accompany the report.
