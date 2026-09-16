# LLM Human Rights Research: ECHR Case Evaluation

This repository contains the code and data for evaluating how large language models (LLMs) judge real European Court of Human Rights (ECHR) cases.

## Run readiness

The 1,000 evaluation targets and the summary-only three-turn sycophancy runner are
ready for execution. Full summarization-quality sign-off remains open because the
extractive-control artifact and atomic-coverage measurements have not been produced.

### Canonical target contract

- Use `data/processed/echr_unified.json`: exactly 1,000 atomic targets from 947 judgments.
- Each target is one `judgment × respondent State × provision × sub-conclusion`.
- The unique key is `(item_id, target_respondent_code, article_full, target_issue)`.
- Every row explicitly records `target_respondent`, `target_provision`, `target_issue`, `target_question`, and `target_status=verified`.
- Article 41 is not a prediction target. All former Article 41 rows were retargeted to verified merits sub-conclusions while preserving 1,000 rows and the annual distribution.
- Use only `data/processed/summaries_dsv41flash.json`: one reviewed DeepSeek V4.1 Flash summary per judgment. Reuse it for every target sharing the same `item_id`.
- Existing results and checkpoints predate this target contract. Start in a new output directory.

The Cilei and Rosip Article 13 target, for example, now explicitly asks about the
Republic of Moldova and the second applicant's effective-remedy complaint. Russia
is not an alternative target for that row.

### Target model roster

The perturbation and sycophancy runs use the same six target models:

- `openai/gpt-5.6-sol`
- `anthropic/claude-opus-4.8`
- `deepseek/deepseek-v4-pro`
- `deepseek/deepseek-v4-flash`
- `qwen/qwen3-235b-a22b`
- `qwen/qwen3-32b`

Both Qwen targets are Qwen3 models. Qwen3-8B is excluded. The adaptive challenger
is not a target model.

### Current gates

| Gate | Evidence | Status |
| --- | --- | --- |
| Atomic target scope | 1,000 unique target keys; one respondent, provision, and sub-conclusion per row; 0 Article 41 targets | PASS |
| Dataset and summary coverage | 1,000/1,000 targets and 947/947 usable single summaries | PASS |
| Current-judgment leakage review | Reviewed summary and source records, including the 12 adjudicated procedural-history cuts | PASS |
| Outgoing perturbation payloads | Fake transport exercises baseline, summary, three framing arms, and reconsideration without exposing gold labels | PASS |
| Sycophancy prompt preflight | All 1,000 targets × 9 conditions fit the 55-word challenge budget at all three turns | PASS |
| Extractive control artifact | Builder preflight passes, but no complete current artifact exists | OPEN |
| Atomic summary coverage | No current abstractive/extractive coverage result exists; the full-judgment source is absent | OPEN |

The extractive control and atomic coverage are measurement arms, not substitutes
for the atomic target audit. Do not claim that all summaries passed those two
quality controls until their artifacts and acceptance rule exist.

### Three-turn sycophancy contract

- Every trajectory has exactly three challenge turns.
- One saved initial response is forked into matched static and adaptive trajectories.
- Every target and challenger call uses the reviewed summary, never the full judgment.
- The respondent State, provision, issue, opposing conclusion, condition, and pressure remain fixed for all three turns.
- Adaptive challenger output must echo the exact target fields; mismatches are rejected and retried.
- Static and adaptive outputs and metrics are written separately. They must never be pooled into one sycophancy rate.
- The run continues through turn 3 after a reversal so persistence and recovery remain observable.
- Perturbation `rq3` is a separate one-message diagnostic and is not the sycophancy experiment.

Run the offline checks before any paid calls:

```bash
python scripts/validate_eval_dataset.py --require-complete
python scripts/verify_model_input_payloads.py
python -m pytest -q
```

Launch one target model with the summary-only sycophancy runner:

```bash
python experiments/run_adversarial_opinion.py \
  --model openai/gpt-5.6-sol \
  --base-url "$OPENAI_COMPATIBLE_BASE_URL" \
  --api-key-env OPENAI_API_KEY \
  --challenger-model "$FROZEN_CHALLENGER_MODEL" \
  --workers 69 \
  --output-dir data/experiments/syco
```

Each model directory contains `initial.jsonl`, `static.jsonl`, `adaptive.jsonl`,
`static_metrics.json`, and `adaptive_metrics.json`. The two modes share the saved
initial response but otherwise remain independent.

### Perturbation analysis

The six-model family declares 30 comparisons: 6 summarization, 18 framing, and 6
reconsideration comparisons. The analyzer validates all 1,000 atomic targets,
uses substantive targets for headline hypothesis tests, reports Articles 34 and
38 separately, and applies Benjamini-Hochberg once across the complete family.

```bash
python scripts/analyse_perturbation_run.py --run-dir "$OUT"
```

See [DATA_SPLITS.md](DATA_SPLITS.md), [the input repair record](docs/INPUT_REPAIR.md),
[the summary protocol](docs/SUMMARIZATION_PROTOCOL.md), and
[the sycophancy methodology](docs/ADVERSARIAL_OPINION.md).

## Repository structure

```text
configs/evaluation_dataset.json            Atomic target contract and annual counts
configs/target_scope_overrides.json         Reviewed target disambiguations
configs/adversarial_opinion_conditions.json Nine fixed sycophancy conditions
data/processed/echr_unified.json            1,000 atomic targets
data/processed/summaries_dsv41flash.json    947 single summaries
data/audits/target_scope_audit.json         Per-row target evidence
experiments/run_perturbation_openai.py      Shared 0-100 perturbation runner
experiments/run_adversarial_opinion.py      Summary-only three-turn sycophancy runner
scripts/analyse_perturbation_run.py         Full-family perturbation analysis
scripts/build_extractive.py                 Verbatim-source control builder
scripts/build_atomic_coverage.py            Shared-claim coverage instrument
```

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
