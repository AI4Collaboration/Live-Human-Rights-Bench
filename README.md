# LLM Human Rights Research: ECHR Case Evaluation

This repository contains the code and data for evaluating how large language models (LLMs) judge real European Court of Human Rights (ECHR) cases.

## Run readiness: NOT READY

The approved single-summary release is complete and leakage-reviewed, but the
summarization-quality controls and the three-turn sycophancy runner are not yet
complete. Do not start the full paid run.

### Canonical input

- Use `data/processed/echr_unified.json`: 1,000 case-article instances from 947 judgments.
- Use only `data/processed/summaries_dsv41flash.json`: one approved DeepSeek V4.1 Flash summary per judgment, covering all 1,000 instances.
- Join instances by `(item_id, article_full)`. Reuse the same judgment-level summary for every article instance with the same `item_id`.
- Every sycophancy target and adaptive challenger must receive the approved summary, the target provision, and that trajectory's conversation only. They must not receive the full judgment or `full_case_text_no_verdict`.
- Existing target-model results and checkpoints are not results for this release. Start every current-release run in a new output directory.

### Target model roster

The same six target models are used for the perturbation and sycophancy runs:

- `openai/gpt-5.6-sol`
- `anthropic/claude-opus-4.8`
- `deepseek/deepseek-v4-pro`
- `deepseek/deepseek-v4-flash`
- `qwen/qwen3-235b-a22b`
- `qwen/qwen3-32b`

The two Qwen targets are from the same Qwen3 generation. Qwen3-8B is excluded.
The adaptive challenger is not part of this target roster.

### Summary quality gates

| Gate | Current evidence | Status |
| --- | --- | --- |
| Release identity and coverage | `validate_eval_dataset.py --require-complete` verifies 947/947 usable summaries and coverage of all 1,000 instances. | PASS |
| Current-judgment leakage review | All 947 selected summaries are bound to accepted conclusion, merits-reasoning, and sufficient-facts review records. | PASS |
| Procedural-history leakage | The adjudicated cuts removed 2,456 characters from 11 judgments and 12 instances. Relocating every verified detector quote finds 0 leak rows; the remaining 12 review spans were read and found harmless. | PASS |
| Extractive format preflight | The current span-based parser accepts 947/947 reviewed sources. | PASS, preflight only |
| Extractive control artifact | No current-release extractive summary artifact has been generated and verified. | MISSING |
| Atomic coverage | No abstractive or extractive atomic-coverage results exist. The required full-judgment source file is not included in the release. | MISSING |

The extractive control is a separate verbatim-input arm, not a pass/fail test for
each abstractive summary. Atomic coverage produces factual-retention rates, not an
automatic pass. If atomic coverage is a launch gate, freeze its acceptance rule
before inspecting results. Until the extractive artifact, atomic measurements, and
acceptance rule are complete, do not claim that all summaries passed the full
summarization-quality protocol.

### Sycophancy execution contract

- Every sycophancy trajectory has exactly three challenge turns. `T = 3` is fixed, not a command-line choice.
- Generate one initial target response from the approved summary, then fork that exact saved response into one static trajectory and one adaptive trajectory.
- The static arm uses the frozen turn-1 template followed by the frozen later-turn template on turns 2 and 3. It never reads adaptive replies.
- The adaptive arm generates one challenge at a time from its own full transcript and the same approved summary. It never reads static replies.
- Keep the case, summary, target provision, initial response, opposing position, trigger, cue, pressure level, target model, decoding settings, and response limits matched across arms.
- Continue through turn 3 after a reversal so that persistence and recovery remain observable.
- Do not use the perturbation runner's `--rq rq3` mode as the sycophancy experiment. It is a different one-message diagnostic.

Static and adaptive results must be stored and reported separately. For each mode,
report scheduled trajectories, eligible decided initial responses, complete
three-turn trajectories, incomplete trajectories by reason, turn-1/turn-2/turn-3
persuasion, any-turn persuasion, final-turn persuasion, first reversal, persistence,
recovery, abstention transitions, score movement, refusals, malformed outputs,
transport failures, token use, latency, and cost. Do not publish a pooled
"sycophancy rate." A matched static-versus-adaptive comparison may be reported only
as a separate comparison over the intersection of complete eligible trajectories.

### Remaining launch blockers

1. Generate and verify the full 947-judgment extractive control.
2. Supply the full-judgment source required by the atomic instrument, then run atomic coverage for both abstractive and extractive summaries on the same claims.
3. Freeze the atomic-coverage acceptance rule if it is used as a launch gate.
4. Implement the summary-only three-turn sycophancy runner, response parser, resumable checkpoints, separate static/adaptive outputs, and separate metrics.
5. Exercise the complete sycophancy runner with a fake transport and verify every outgoing message before any paid call.

## Current evaluation dataset: year-balanced, DeepSeek summaries

**Use `data/processed/echr_unified.json` for all new experiments.** This frozen pool contains **1,000 case-article instances from 947 judgments**. It samples **67-68 instances per year in 2012-2025**, plus **57 in the partial 2026 window**. The paired summary file is `data/processed/summaries_dsv41flash.json`, generated by `deepseek/deepseek-v4.1-flash`. This selection prioritizes near-uniform year coverage, not summarizer performance.

The [dataset manifest](configs/evaluation_dataset.json) pins both input files and the exact annual counts. Check them without model calls:

```bash
python scripts/validate_eval_dataset.py --require-complete
```

Keep the same case-article pool across models and perturbation arms. Identify instances by `(item_id, article_full)`; `pair_id` alone is not unique. The selected main protocol uses **one summary per judgment: 947 summaries covering all 1,000 instances**. Read the [input repair protocol](docs/INPUT_REPAIR.md) before running.

**Summarization faithfulness uses two complementary checks, not repeated summary draws:** an **extractive control** retains verbatim source passages, and the **atomic coverage instrument** measures retained source facts, including those referenced in the Court's assessment. Both consume one summary per judgment. [Exact commands and data flow](docs/SUMMARIZATION_PROTOCOL.md).

`scripts/run_roster.sh` launches the perturbation rescore only. It does not launch the three-turn sycophancy experiment. [Full dataset contract and year counts](DATA_SPLITS.md#current-evaluation-pool-selected-2026-09-15).

## Start here: Part 3, adversarial opinion and sycophancy

The [methodology](docs/ADVERSARIAL_OPINION.md) and [prompt pack](configs/adversarial_opinion_prompts.json) define the current pressure and influence-cue taxonomy. Prompt construction is implemented, but the summary-only three-turn execution and reporting pipeline is not.

### Offline prompt preview

```bash
# Three-turn low-pressure Baseline trajectory
python scripts/preview_adversarial_prompts.py --turns 3 --word-budget 60 --pressure low --strategy Baseline

# Three-turn high-pressure Authority trajectory
python scripts/preview_adversarial_prompts.py --turns 3 --word-budget 60 --pressure high --strategy Authority

# Offline prompt checks
python -m unittest discover -s tests -p "test_adversarial_prompts.py" -v
```

The preview makes no model calls. There is no Section 5 launch command yet.

## Current single-summary rescore

Use one fixed summary for each of 947 judgments, covering the same 1,000
case-article instances. No target model writes or selects its own summary.
[Faithfulness controls and exact commands](docs/SUMMARIZATION_PROTOCOL.md).

The current six-model family declares **30 comparisons: 6 summarization, 18
framing, and 6 reconsideration**. Every q-value is computed together from fresh,
matched responses for the approved single-summary release.

The [family manifest](configs/perturbation_analysis.json) is the source of truth
for models, conditions and references. It specifies Qwen3-32B,
Qwen3-235B-A22B, DeepSeek V4 Flash, DeepSeek V4 Pro, GPT-5.6 Sol and Claude Opus 4.8.
Both Qwen evaluators are from the Qwen3 generation; Qwen3-8B is excluded.
All six evaluators are configured at 69 workers, with six models launched concurrently.
The target sample count and paid-run budget must be confirmed before launch.
One versus several target responses is independent of the one-summary constraint.

```bash
python scripts/validate_eval_dataset.py --require-complete
python scripts/verify_model_input_payloads.py
python scripts/analyse_perturbation_run.py --run-dir "$OUT"
```

The analyzer requires all models, all declared conditions, the exact instance set,
complete rating samples and matching input/run provenance. It derives accuracy,
alignment and McNemar p-values from raw ratings, then applies BH once to the
entire family. It refuses to produce q-values from a partial run. No results for
the repaired input release are currently claimed. See
[statistical methodology](STATISTICAL_METHODOLOGY.md).

## Repository structure

```text
configs/evaluation_dataset.json       Approved input identity and annual counts
configs/perturbation_analysis.json    Full comparison family and model roster
data/processed/echr_unified.json      1,000 fixed case-article instances
data/processed/summaries_dsv41flash.json   947 single summaries
data/processed/input_release.json    Hash-bound input approval
data/audits/leakage_20260915/          Source and summary review evidence
experiments/run_perturbation_openai.py    Shared 0-100 evaluation runner
scripts/analyse_perturbation_run.py   Full-family rescore analysis
scripts/build_extractive.py          Verbatim-source control builder
scripts/build_atomic_coverage.py     Shared-claim coverage instrument
```

## Current prompts and result format

The perturbation commands use the prompts and 0-100 scoring rules in
`experiments/run_perturbation_openai.py` and `experiments/scoring.py`. They do not
implement the three-turn sycophancy experiment. Perturbation results are
per-instance JSON records with raw rating lists and exact
`item_id` plus `article` keys; a case-article key must be unique in the frozen
cohort. The input manifest also preserves the full provision identifiers.

## Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up API keys
cp .example.env .env
# Edit .env and add your API keys:
# OPENAI_API_KEY=your_key_here
# OPENROUTER_API_KEY=your_key_here
```

## Requirements

- Python 3.10+
- OpenAI API key (for GPT models)
- OpenRouter API key (for Claude and DeepSeek)
- See `requirements.txt` for package dependencies

## Citation

If you use this code or data, please cite:

```
[Citation to be added upon publication]
```

## License

[License to be added]

## Contact

For questions or issues, please open a GitHub issue or contact [contact information].

## Acknowledgments

This research uses the ECHR case database and evaluates state-of-the-art language models' ability to predict human rights violations.
