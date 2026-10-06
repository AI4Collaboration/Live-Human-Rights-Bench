# Paraphrase fact preservation

Input: [`data/processed/paraphrase_texts.jsonl.gz`](../../data/processed/paraphrase_texts.jsonl.gz)
(commit `325f26b`): 1,000 targets (947 judgments) x 4 conditions
(`original`, `light`, `medium`, `heavy`), produced by
[`experiments/paraphrase_run.py`](../../experiments/paraphrase_run.py) with
`openai/gpt-5.6-sol`. The generator rewrites `text[:50000]` in chunks of about
3,000 characters split on line breaks, with `max_tokens=4000` per chunk, so every
check here compares a paraphrase with that same 50,000-character prefix.

The number check is deterministic and makes no model calls:

```bash
python quality_control/paraphrase/check_preservation.py \
    data/processed/paraphrase_texts.jsonl.gz quality_control/paraphrase
```

It extracts application numbers, dates (normalised across `24/09/2012`,
`24 September 2012` and `September 24, 2012`), numbers and capitalised names from
both sides and reports recall against the source. Both sides get the same
normalisation first: paragraph numbering, footnote markers and thousands
separators are removed, and words or paragraph numbers glued to numbers in
sources without line breaks are split off (`STRASBOURG17 October 2019`,
`October 2002.13. On`). [`per_row.csv`](per_row.csv) has one row per target and
condition; [`summary.json`](summary.json) has the aggregates and the target lists.
`tiktoken` is optional and only fills the reference column `output_tokens_o200k`.

## Finding: 26 targets were cut at the generator's output cap

When a chunk is long enough, its paraphrase hits the 4,000-token cap and loses
its end. `chunks()` splits only on line breaks, and many sources have none, so a
whole record of 12,000-50,000 characters goes out as one chunk. 104 targets have
a chunk over 12,000 characters. Two signals mark a cut:

* `tail_lost`: under half of the dates and numbers that appear only in the last
  30% of an oversized chunk survive. As a control, targets without an oversized
  chunk never fall below 0.5 on the same measure taken over the last 20% of the
  source (731 targets with at least three such numbers).
* `end_cut`: a single oversized chunk whose paraphrase stops mid-sentence ("...
  the Code of Criminal Procedure provides that").

26 targets (25 judgments) carry at least one signal: 26 in `light`, 23 in
`medium`, 22 in `heavy`. They are listed under `truncated` in `summary.json`. 19
of them keep less than 80% of the source length in some condition, down to 35%;
one of these, `001-165951`, lost the end of its fourth chunk of six rather than
the end of the text. The other 7 keep 80-98% of the length. Six stop before the
source does: `001-127809` loses most of its last fifth, the rest a closing
passage. `001-213901` is flagged inside its text, only in `light` and on three
numbers. The cut single-chunk paraphrases measure 3,700-3,960 tokens by
`o200k_base`, which is the cap as counted by a different tokenizer.

For these targets the accuracy change mixes rewording with missing facts. The
options are to exclude them from the paraphrase analysis and say so, or to
regenerate them with chunks split on sentences.

## Results

Mean recall / share of targets with nothing lost, all 1,000 targets:

| Measure | light | medium | heavy |
| --- | --- | --- | --- |
| Application numbers | 0.992 / 98.5% | 0.992 / 98.1% | 0.993 / 98.6% |
| Dates (distinct) | 0.993 / 95.9% | 0.990 / 87.5% | 0.994 / 96.4% |
| Salient numbers (3+ digits or decimals, distinct) | 0.984 / 92.8% | 0.983 / 89.7% | 0.986 / 93.4% |
| All numbers (with counts) | 0.932 / 53.5% | 0.912 / 29.6% | 0.923 / 39.7% |
| Capitalised names (distinct) | 0.979 / 46.1% | 0.943 / 19.3% | 0.939 / 18.5% |
| Median length ratio | 0.987 | 0.981 | 0.985 |
| Preamble or refusal text | 0.0% | 0.1% | 0.0% |

Without the 26 cut targets (974 remain), mean recall is 0.999 / 0.999 / 1.000
for application numbers, 0.999 / 0.995 / 0.999 for dates and
0.995 / 0.993 / 0.996 for salient numbers. At most 5 targets per condition keep
under 80% of their salient numbers.

Preservation does not fall as rewrite strength rises. `medium` loses slightly more
than `heavy` on dates and on numbers counted with repeats.

## What the other flags show

* **Added numbers** (3.5% / 10.0% / 6.8% of rows have a salient number or date
  absent from the source). Every one traced in a sample of ten is faithful: the
  paraphraser writes out elided years ("On 15, 22 and 28 February and 6, 7, 12
  and 30 March 2007" gets a year on each date), changes formats ("3,10 pm." to
  "3.10 p.m.", "EUR 3.3 million") and fixes typos in the source
  ("8 Septembre 2009"). They are flags for reading, not a hallucination
  rate.
* **New verdict vocabulary** (5.9% / 8.0% / 10.7% of rows use "violated" or
  "breach" more often than the source). In a 12-row sample, every case rewords an
  applicant's complaint ("complained that his right ... had been violated") or a
  domestic court's holding. None states a Court finding. This is a shift in tone,
  not verdict leakage, but it grows with rewrite strength.
* **Names**: most losses are judge names from the chamber composition. Judgment
  boilerplate is removed by a stoplist. Party names are not measured separately.
* **Instruction**: only `heavy` asks to "keep every fact and number"; `medium` asks
  to "keep all facts"; `light` says nothing about facts.

## Claim-level check

The number check cannot see a fact without a number or a name, or a fact whose
parts survive in the wrong arrangement. [`claim_coverage.py`](claim_coverage.py)
covers both, using the summary arm's method (`experiments/atomic.py`):

1. Atomic claims are extracted from the source, from up to 16 numbered paragraphs
   per judgment chosen at random inside the 50,000-character prefix (at most 6
   claims per paragraph, as for summaries).
2. Each claim is checked against each paraphrase by a verifier that never sees
   the source. The prompt says a claim with its actor, object, date, figure or
   outcome rearranged is not supported.
3. Every claim the original supports but a paraphrase does not gets a second
   look: `absent` (the event is not reported), `altered` (reported with a part
   changed) or `present` (a verifier miss).

Extractor and verifier are `qwen/qwen3-235b-a22b`, the model of the summary
claim check, called the same way (default reasoning, temperature 0) through
OpenRouter. It is not the paraphraser. The run covers 947 judgments, 1,000
targets and 69,106 claim-target pairs, with a median of 78 claims per target and
no unverified batch. It cost $94.51 including a 20-judgment pilot.

```bash
python quality_control/paraphrase/claim_coverage.py \
    --model qwen/qwen3-235b-a22b --api-key-env OPENROUTER_API_KEY --out <run dir>
python quality_control/paraphrase/claim_report.py --run quality_control/paraphrase/claims \
    --out quality_control/paraphrase/claims/summary.json \
    --per-target quality_control/paraphrase/claims/per_target.csv
```

[`claims/claims.jsonl.gz`](claims/claims.jsonl.gz) holds every claim and verdict,
[`claims/per_target.csv`](claims/per_target.csv) one row per target and
[`claims/summary.json`](claims/summary.json) the aggregates below.

### Results

Retention is the share of claims the verifier finds in the original that it
still finds in the paraphrase, averaged per target. Brackets are 95% intervals
from a bootstrap over targets.

| | light | medium | heavy |
| --- | --- | --- | --- |
| 974 targets, not cut | 0.995 [0.994, 0.996] | 0.993 [0.992, 0.994] | 0.992 [0.991, 0.993] |
| same, verifier misses credited | 0.998 | 0.997 | 0.996 |
| 26 cut targets | 0.905 [0.854, 0.944] | 0.914 [0.864, 0.952] | 0.900 [0.843, 0.945] |

The verifier finds 99.2% of the claims in the original text itself, which sets
its noise floor. Retention falls slightly with rewrite strength, which the
number check did not show.

**Controls.** The cut targets serve as a known-bad case. On them, `heavy` keeps
0.98-0.99 of claims from the first 40% of the source, 0.79 at 60-80% and 0.66 in
the last fifth. On the other targets it keeps 0.99 at every position. A second
control rewrote 300 claims with roles or attributes swapped and checked them
against the original. The verifier accepted 14.7%, so it catches about 85% of
rearranged facts.

**What the losses are.** In the 974 targets that were not cut, `heavy` loses 471 of
66,369 claims: 271 `present`, 131 `altered`, 69 `absent`. `light` and `medium` show
the same pattern (347 and 418 losses). Read against the texts, the labels
overstate real changes. In 20 sampled `altered` claims, about two are genuine.
Both sit in tables of sources without line breaks, where the source glues a
cell number to a date (`25007/06/06` for cell 250 from 7 June 2006) and the
paraphrase splits it wrongly (cell 500). The rest are claims the extractor
misread from the source, or wording the verifier did not match. In 10 sampled
`absent` claims, one is a real omission ("on the various dates indicated in the
appended table"). The rest are present, or misread at extraction.

Taken together, rearranged facts are at most 0.2% of claims (131 of 66,369, of
which most are noise) and dropped facts at most 0.1%, both under the verifier's
own noise. The one material loss in the paraphrase arm is the 26 cut targets.

## Not covered

Claims come from at most 16 paragraphs per judgment, so a loss confined to an
unsampled paragraph is missed in that target. The claim check estimates rates
across targets; it does not certify any single paraphrase. The manual reading
covers 30 labelled claims, enough to show the labels overstate real changes, not
to estimate the real rate precisely.
