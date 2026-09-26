# Data and result inventory

## Current inputs

| Artifact | Contents | Use |
| --- | --- | --- |
| [Canonical cases](processed/echr_unified.json) | v1.0: 1,000 targets from 947 judgments | Full-case evaluation |
| [Selected abstractive summaries](processed/summaries_dsv41flash.json) | 947 summaries | Summary evaluation and adversarial opinion |
| [Extractive controls](processed/summaries_extractive_leakchecked_20260916.json) | 947 extracts | Factual-retention comparison |
| [Human annotations](annotation/annotation_merged.csv) | Returned paragraph-link judgments | [Validation analysis](../docs/ANNOTATION.md) |

The [release manifest](../configs/releases/v1.0.json) pins the inputs.
The [task contract](../DATA_SPLITS.md) defines target identity and labels.
[Audit evidence](audits/README.md) records source review and target verification.

## Published experiment outputs

| Suite | Location | Coverage and interpretation |
| --- | --- | --- |
| Baseline and summary | [Primary models](experiments/unified_fullcase_latest/) | Six models on v1.0 |
| Baseline and summary, earlier models | [Earlier models](experiments/unified_fullcase_oldmodels/) | GPT-4o mini and GPT-4.1 mini |
| Paraphrasing | [Primary models](experiments/paraphrase/), [earlier models](experiments/paraphrase_oldmodels/) | Original, light, medium and heavy arms |
| Country Swap | [Original suite](experiments/stateswap_summary/), [earlier models](experiments/stateswap_oldmodels/) | Original, US, Russia and Ukraine arms |
| Country Swap follow-ups | [Türkiye](experiments/stateswap_summary_turkey/), [UK](experiments/stateswap_summary_uk/) | Three GPT models; each run has its own original-summary arm |
| Three-turn adversarial opinion | [Main score-only suite](experiments/syco_full_latest/) | Six models, 11 conditions, Static and Adaptive |
| Additional opinion controls | [Controls](experiments/syco_controls/) | Separate initial sampling; not continuations of the main run |
| Applicant-nationality controls | [Applicant substitution](experiments/stateswap_applicant/) | Three GPT models; separate from respondent-country substitution |
| One-turn nationality cues | [Nationality](experiments/syco_nationality/) | Earlier models; nationality combined with lawyer identity |
| Reasoning-enabled opinion runs | [Opus-4.6](experiments/syco_cot_opus/), [V4-Flash](experiments/syco_cot/) | Fresh initial responses; adaptive coverage remains partial |

Use the [analysis directory](../analysis/README.md) for exact valid cohorts,
exclusions, denominators and source hashes. The reasoning-run reversal rates
and text-availability cohorts are separate from the main score-only results.
Country Swap manuscript comparisons use the
[context-screened cohorts](../analysis/stateswap_context/REPORT.md).

## Inputs awaiting publication

- Generated `processed/paraphrase_pairs.json` for the published paraphrase runs.
  Regenerating paraphrases would create different inputs.
- Claim-level summary-coverage checkpoints described in the
  [summarization protocol](../docs/SUMMARIZATION_PROTOCOL.md). The selected
  summaries, extractive controls and paragraph-link annotations are released.

Country Swap inputs are reconstructed from canonical summaries and the
[published transformation](../docs/STATESWAP.md). The obsolete
`processed/echr_stateswap.json` is not an input to these runs.

## Deprecated sources

The six older Hugging Face releases are **deprecated as evaluation inputs**.
The [source register](../docs/DATA_SOURCE_STATUS.md#deprecated-hugging-face-releases)
records their exact revisions and replacements. Superseded local pilot files
are not part of v1.0.
