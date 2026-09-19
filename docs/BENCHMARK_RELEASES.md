# Benchmark releases

## LiveHumanRightsBench v1.0

**v1.0** names the current fixed evaluation snapshot: **1,000 targets from 947
ECtHR judgments**, dated **10 January 2012 to 21 May 2026**, covering 24
provisions and 46 respondent States. The outcomes are 700 violations and 300
no-violations. The name was assigned on 19 September 2026 to the existing cohort;
no case, label, summary or experiment result was changed by this designation.

The [release manifest](../configs/releases/v1.0.json) fixes the input paths and
SHA-256 hashes. The [cohort specification](../configs/evaluation_dataset.json)
retains annual counts and target definitions. Existing checkpoints continue to
use `echr-unified-atomic-targets-20260916` as their internal dataset identifier.

LiveHumanRightsBench is a construction and evaluation pipeline. **1,000 is the
size of v1.0**, and subsequent releases can select different cohort sizes and
add newly published judgments. New model results can evaluate the same v1.0
inputs; changed cases, targets, labels or designated model inputs receive a new
release manifest. A result commit and a dataset version therefore identify
different parts of an experiment.

## Time window and model cutoffs

The [cutoff register](../configs/model_knowledge_cutoffs.json) records verified
provider dates, source URLs and date granularity. The
[model and time-window analysis](../analysis/model_time_windows/REPORT.md)
compares eight models on identical v1.0 targets. A post-cutoff target has a
decision date later than the provider date; month-only cutoffs use month-end.

The cutoff analysis focuses on **the two earlier models**. v1.0 contains
214 targets after GPT-4o mini's documented cutoff and 159 after GPT-4.1 mini's.
The six primary models, including Claude Opus 4.6 and GPT-5.6 Sol, supply
reference results on those same case splits. Temporal results include class
counts, class recalls and balanced accuracy alongside ordinary accuracy.
Knowledge dates locate the evaluation window; they do not establish whether
an individual judgment was in training.

The register retains verified provider dates for the reference models as
source metadata, including the distinction between Claude's reliable-knowledge
and training-data dates. The analysis partitions cases using the two earlier
OpenAI cutoffs only. Dates for DeepSeek V4 and Qwen3 were not established in
the checked primary sources, so no knowledge cutoff is assigned to them.

## Input status

GitHub holds the designated v1.0 inputs. No Hugging Face mirror currently
represents v1.0. The [source-status register](DATA_SOURCE_STATUS.md) identifies
the deprecated releases and their current replacements.
