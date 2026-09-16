# Legacy experiment runners

These provider-specific perturbation runners and the native-Sol prompt pilot are
historical. They predate the atomic target contract and must not be used for the
current release.

Current execution uses two provider-agnostic entry points:

- `experiments/run_perturbation_openai.py`
- `experiments/run_adversarial_opinion.py`

The archived pilot outputs are retained only as prompt-development provenance.
