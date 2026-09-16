# Historical input-repair tooling

This directory preserves the one-off source and summary repair programs used for
the 2026-09-15 leakage repair. They rely on the retired hash-bound publication
format and are not valid entry points for the current atomic-target release.

Current validation and execution use:

- `scripts/validate_eval_dataset.py`
- `scripts/verify_model_input_payloads.py`
- `experiments/run_perturbation_openai.py`
- `experiments/run_adversarial_opinion.py`

The historical tests are retained beside the archived programs as audit context.
