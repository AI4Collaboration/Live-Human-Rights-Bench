# Rebuttal package

Updated 8 November 2026. This package covers all concerns and questions in the
three reviews. It combines existing-record analyses with one completed set of
focused static controls. The new collection cost **$23.33**; no further model
calls are scheduled in this package.

The [ICLR 2027 author guidelines](https://iclr.cc/Conferences/2027/AuthorGuidelines)
allow ten main-text pages during rebuttal and discussion. The revised manuscript
uses this allowance for the targeted-control comparison in the main text.

## Read first

- [Responses by reviewer](RESPONSES.md) contain the response text and identify
  the revisions supporting each answer.
- [Review tracker](review_tracker.csv) maps every concern to its answer and
  evidence. EmoP's new-judgment question remains an empirical task for a data
  and evaluation owner; its response states the current evidence accurately.
- [Analysis report](../../analysis/rebuttal_20261107/REPORT.md) gives counts,
  denominators and uncertainty for every new comparison.
- [Work to assign separately](DELEGATED_TASKS.md) specifies the new-release
  task and distinguishes it from optional recovery of already saved records.

## Evidence and reproduction

The [frozen experiment protocol](EXPERIMENTS.md) selected 50 judgments from 795
eligible shared judgments before new collection. The
[raw run](../../data/experiments/rebuttal_20261107/) contains the manifest,
saved initial replies and full request/response records. All 1,300 planned
trajectories were attempted; 1,275 have three valid scores. Comparisons use
their stated shared-case denominators and retain failures in the raw records.

The [release protocol](RELEASE_PROTOCOL.md) explains how source candidates
become a reviewed release and how hashes, target definitions and evaluation
settings are held consistent. Its offline reconstruction uses v1.0 only.

```bash
python analysis/analyze_rebuttal_existing.py
python analysis/analyze_rebuttal_controls.py
python analysis/build_rebuttal_report.py
python analysis/verify_rebuttal_package.py
python -m pytest -q tests/test_rebuttal_controls.py tests/test_eval_dataset.py
```

These commands make no model calls. The result generators read pinned source
records and preserve the distinction between the original experiments and
the new continuations of saved initial replies.

## Manuscript changes

The revised paper identifies explicit replacement demands wherever it reports
the corresponding high reversal rate. It adds the opinion-only comparison
and evaluation-framing result to the adversarial-opinion section. Appendix
material supplies repeated-conversation results, all new control conditions,
sampling and missing-data rules. Existing appendix sections now include the
independent paraphrase-verifier evidence, the 540-target sensitivity analysis,
reasoning-text availability and the release-consistency check.

The benchmark and combined evaluation are the contribution. The responses do
not claim that perturbation itself is a new algorithm or that written
reasoning identifies the mechanism behind a model's judgment.
