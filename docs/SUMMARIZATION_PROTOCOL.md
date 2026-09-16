# One summary, two faithfulness checks

The main experiment uses **one fixed DeepSeek summary per judgment**: 947 texts
for 1,000 atomic targets. The same text is reused across target models and every
target sharing the judgment's `item_id`. There is no best-of-three selection or
cross-version pooling. Loaders and analysis reject multi-summary files and repeated
atomic target keys.

| Component | Input and output | Question |
| --- | --- | --- |
| Main abstractive arm | Reviewed source → one approximately 500-word summary | How does summarization change judgment? |
| Extractive control | Same source → selected verbatim paragraphs | Does the effect remain without newly generated factual assertions? |
| Atomic coverage | Source facts → atomic claims → support in each summary | Which factual claims survive, including those from paragraphs cited by the Court? |

The two controls address different aspects of faithfulness. Verbatim extraction
prevents invented text but can omit context. Atomic coverage estimates fact
retention; a high score is not a proof that every legally material fact survived.
Neither is replaced by repeated stochastic summaries. The input-leakage gate
separately excludes the current Court's conclusions and merits reasoning.

## Use the approved summary

```bash
python scripts/validate_eval_dataset.py --require-complete
```

Pass `data/processed/summaries_dsv41flash.json` to the evaluation runner's
`--summaries` argument. Use a fresh result directory and rerun the matched
baseline. The semantic input gate requires the exact active target cohort and the
reviewed canonical summary text. Target-model results and faithfulness measurements
have not yet been produced for this release.

## Build one extractive control

The current span-based parser passes the offline format preflight for all 947
reviewed judgments. This confirms source compatibility only. It does not create
the extractive summaries or constitute an extractive-control result.

```bash
python -X utf8 scripts/build_extractive.py --cases data/processed/echr_unified.json --summarizer deepseek/deepseek-v4.1-flash --out data/processed/summaries_extractive_leakchecked_20260916.json --check-only
```

After the preflight passes, the following command makes paid selector calls. It
selects paragraphs from the reviewed, 50,000-character source input, assembles
them in source order, and records selected and omitted paragraph numbers. Failed
calls are not successful extracts.

```bash
python -X utf8 scripts/build_extractive.py --cases data/processed/echr_unified.json --summarizer deepseek/deepseek-v4.1-flash --api-key-env OPENROUTER_API_KEY --out data/processed/summaries_extractive_leakchecked_20260916.json
```

Before evaluation, the input gate reassembles each selected extract from the
current source and checks exact equality. Extracts without matching selection
records are rejected. Evaluate the control with the same
runner and cohort, passing this file to `--summaries` in a separate output
directory. Check and report extraction coverage before comparing arms.

## Measure atomic coverage

Choose an independent coverage model, different from the summarizer. Set
`COVERAGE_MODEL` to its provider identifier. Supply `FULL_JUDGMENTS_CSV`, a file
with `item_id` and `full_text` columns, from the full-judgment source corpus; this
file is not bundled with the repaired benchmark release. These full judgments are used
**only by the coverage instrument** to locate Court-to-fact back-references,
never as inputs to the benchmark target. Sampled fact paragraphs must also occur
in the exact source input available to the summarizer.

Run the two commands sequentially in the **same output directory**. The second
run reuses the first run's extracted claims, so support is compared claim-for-claim.
Source, claim-extraction settings and summary identities are checked on resume.
These commands make paid coverage-model calls. Use the same eligible judgment
set and settings for both variants; incomplete extraction needs resolving first.

```bash
python -X utf8 scripts/build_atomic_coverage.py --full-texts "$FULL_JUDGMENTS_CSV" --summaries data/processed/summaries_dsv41flash.json --variant abstractive --model "$COVERAGE_MODEL" --api-key-env OPENROUTER_API_KEY --out data/experiments/atomic_leakchecked_20260916
python -X utf8 scripts/build_atomic_coverage.py --full-texts "$FULL_JUDGMENTS_CSV" --summaries data/processed/summaries_extractive_leakchecked_20260916.json --variant extractive --model "$COVERAGE_MODEL" --api-key-env OPENROUTER_API_KEY --out data/experiments/atomic_leakchecked_20260916
```

On PowerShell, use `$env:COVERAGE_MODEL` and `$env:FULL_JUDGMENTS_CSV`.
The verifier receives the single summary string and atomic claims, not a list of
alternative summaries, the reference outcome, or a target model's predictions.
Results record overall and Court-referenced fact coverage with their denominators.

## Audit history

The old multi-version generator, cross-version evaluator, and one-off leakage
repair programs are not current entry points. Historical repair tooling is under
`archive/input_repair_20260915/`; its logs remain audit evidence and cannot be
loaded as current evaluation inputs. Use `experiments/run_perturbation_openai.py`
or `experiments/run_adversarial_opinion.py` for current evaluations.
