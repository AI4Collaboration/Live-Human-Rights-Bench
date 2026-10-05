# Paraphrase fact preservation

Input: [`data/processed/paraphrase_texts.jsonl.gz`](../../data/processed/paraphrase_texts.jsonl.gz)
(commit `325f26b`): 1,000 targets (947 judgments) x 4 conditions
(`original`, `light`, `medium`, `heavy`), produced by
[`experiments/paraphrase_run.py`](../../experiments/paraphrase_run.py) with
`openai/gpt-5.6-sol`. The generator rewrites `text[:50000]` in chunks of about
3,000 characters split on line breaks, with `max_tokens=4000` per chunk, so every
check here compares a paraphrase with that same 50,000-character prefix.

The check is deterministic and makes no model calls:

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

## Not covered

This is a surface check. Reworded facts with the same numbers, changed relations
("the applicant" and "the officer" swapped) and dropped sentences without numbers
or names are not detected. A claim-level check like the one for summaries
(`scripts/build_atomic_coverage.py`) would cover them.
