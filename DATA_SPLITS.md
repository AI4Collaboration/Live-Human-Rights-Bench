# DATA_SPLITS.md — LiveHumanRightsBench evaluation splits

This document is the canonical map of the **scaled evaluation sets** for
LiveHumanRightsBench and how each experiment binds to a dataset, a filter, and a
field. It supersedes the 141-pair pilot (`data/processed/echr_cases_final_clean.json`)
for the headline benchmark; the pilot remains valid for the RQ1–RQ3 methodology
checks.

All sets are **verdict-free** (contamination-controlled), built from **public
HUDOC sources only** (redistributable), `seed=42`, reproducible. Both passed a
leakage audit (v1.1, 2026-07-03) that removed verdict-revealing sentences; see
per-dataset changelogs on the Hub.

## Datasets on Hugging Face

| Dataset | Rows | Split | Subset selector |
|---------|------|-------|-----------------|
| [`overthelex/echr-livehrb-static-2k`](https://huggingface.co/datasets/overthelex/echr-livehrb-static-2k) | 2000 | `train` | column `group ∈ {regular, ukr}` |
| [`overthelex/echr-livehrb-temporal-2k`](https://huggingface.co/datasets/overthelex/echr-livehrb-temporal-2k) | 2000 | `train` | columns `group ∈ {regular_temporal, ukr_temporal}`, `bin` |

### `echr-livehrb-static-2k`
- `group == "regular"` — 1000 pairs, **ex-Ukraine**, round-robin stratified by respondent country (`echr-verdict-free`).
- `group == "ukr"` — 1000 pairs, **Ukraine**, round-robin stratified by ECHR article (`echr-ukr-verdict-free`).
- Natural violation / no-violation base rate preserved (base-rate balancing is a separate task).

### `echr-livehrb-temporal-2k`
- `group == "regular_temporal"` — 1000 pairs, ex-Ukraine, `bin` = decision year `2017`…`2026` (100/bin). Per-model pre/post training-cutoff analysis and temporal-drift curves (arXiv:2605.24452).
- `group == "ukr_temporal"` — 1000 pairs, Ukraine, split at Russia's full-scale invasion **2022-02-24**: `bin ∈ {pre_2022, post_2022}` (500 / 500), round-robin by ECHR article — geopolitical-shift axis.

## Field reference (identical schema in both sets)

| Field | Role |
|-------|------|
| `verdict_free_text` | **INPUT** — case text with the conclusion surgically removed (conclusion-scrubbed) |
| `violation_label` | **GOLD** — binary target; score model calls against this |
| `article` | target ECHR article, **bare number with protocol prefixes collapsed** (see [Article field encoding](#article-field-encoding)); e.g. `1` = Article 1 of Protocol 1 (property), not Convention Article 1 |
| `respondent` | respondent state (`UKRAINE` for the `ukr` / `ukr_temporal` groups) |
| `group` | subset selector (see tables above) |
| `bin` | temporal bin — year string \| `pre_2022` \| `post_2022` (temporal set only) |
| `item_id`, `case_name`, `application_number`, `ecli` | identifiers |
| `decision_date`, `importance` | metadata (100% date coverage) |
| `verdict_removal_method`, `verdict_free_length`, `retention_percentage`, length fields | leakage-audit provenance; rows with `+conclusion_scrub` were patched in v1.1 |

> **`violation_label` (confirmed from the parquet):** string, `"violation"` /
> `"no_violation"`. The label split is the intended **natural base rate** (not
> balanced): overall 83.2% violation; `regular` 72.5%, `ukr` 93.8%.

## Article field encoding

> ⚠️ **Read before keying any per-article logic.** The `article` field is a
> **bare number with protocol prefixes collapsed** — full Convention/Protocol
> codes (`P1-1`, `P4-2`, `P7-4`) are **not** preserved. This is inherited from
> the source corpus's HUDOC parse (0 rows carry a `P`/protocol marker). Verified
> on `echr-livehrb-static-2k`:

- `article == "1"` is **Article 1 of Protocol 1 (property)** for ~95%+ of rows
  (e.g. *R & L, s.r.o. v. Czech Republic*, *K.V. Mediterranean Tours v. Türkiye*),
  **not** Convention Article 1.
- `article == "4"` **conflates** Convention Article 4 (slavery / trafficking,
  e.g. *V.C.L. and A.N. v. UK*) with Protocol 4 (freedom of movement / collective
  expulsion, e.g. *Sharifi and Others v. Italy and Greece*).
- `7`, `12`, `18` are the Convention articles in this set, but the field alone
  cannot disambiguate protocol vs Convention — use `case_name` / text if needed.

**Do not key per-article legal tests on this field assuming Convention numbering.**
Planned fix: rebuild the sets preserving full codes (`P1-1`, `P4-2`, `P7-4`, …).
Until then, treat `1` as P1-1 and split `4` by hand for any clean per-right test.

## Article buckets

Report substantive and procedural articles as **separate downstream buckets** —
all models collapse on Art. 41 (balanced acc 0.21–0.42 in the MFT baseline), and
letting procedural articles into the headline number drags substantive results
around. Values below are the field's actual (collapsed) codes, per the note above:

- **Substantive:** `1` (= P1-1, property), `2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 18`
- **Procedural / ancillary (separate bucket):** `34, 38, 41` (also `35, 46` when present)

## Experiment → split map

| # | Experiment | Dataset | Filter | Metric / axis |
|---|------------|---------|--------|---------------|
| 1 | MFT baseline (balanced acc) | static-2k | both groups | balanced acc + violation / no-violation acc + abstention, per model |
| 2 | Ukraine effect | static-2k | `group==regular` vs `group==ukr` | no-violation accuracy delta (the directional prior) |
| 3 | Article bucketing | static/temporal | filter `article` (buckets above) | substantive vs procedural, report separately |
| 4 | Temporal drift | temporal-2k | `group==regular_temporal`, group-by `bin` (year) | balanced acc vs decision year; mark each model's training cutoff |
| 5 | UA geopolitical shift | temporal-2k | `group==ukr_temporal`, `bin ∈ {pre_2022, post_2022}` | pre vs post 2022-02-24 |
| 6 | State-swap counterfactual | static-2k | `group==regular`, substantive articles only | violation/no-violation call under respondent swap (see below) |

## State-swap counterfactual protocol (experiment 6)

Isolates the **country prior** from the **temporal shift** that confounds the raw
Ukraine effect (the UA caseload is mostly post-2022, when the base rate moves too).

1. Base pool: `static-2k`, `group=="regular"`, substantive articles only.
   (Consider dropping `article=="4"` here — it conflates two different rights;
   see [Article field encoding](#article-field-encoding).)
2. Hold `verdict_free_text` (the facts) **fixed**.
3. Pass the respondent state to the model as a **separate prompt field**, and swap
   it `non-UA ↔ UKRAINE`. Do **not** string-edit the country into
   `verdict_free_text` — that introduces surface artifacts and can reintroduce
   leakage.
4. Re-score violation / no-violation against `violation_label` and compare the
   call distribution across the swap.

A pure counterfactual (facts constant, only respondent varies) cleanly separates
"model over-predicts violation for Ukraine" from "base rate shifted after 2022".

## Loading

```python
from datasets import load_dataset

static   = load_dataset("overthelex/echr-livehrb-static-2k", split="train")
temporal = load_dataset("overthelex/echr-livehrb-temporal-2k", split="train")

regular  = static.filter(lambda r: r["group"] == "regular")   # ex-Ukraine
ukr      = static.filter(lambda r: r["group"] == "ukr")        # Ukraine

y2024    = temporal.filter(lambda r: r["group"] == "regular_temporal" and r["bin"] == "2024")
ukr_pre  = temporal.filter(lambda r: r["bin"] == "pre_2022")
ukr_post = temporal.filter(lambda r: r["bin"] == "post_2022")

# NB: bare codes with protocol prefixes collapsed. "1" == P1-1 (property);
# "4" conflates Convention Art 4 and Protocol 4 (see "Article field encoding").
SUBSTANTIVE = {"1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "18"}
PROCEDURAL  = {"34", "35", "38", "41", "46"}
```

## Provenance

- Source corpora: `overthelex/echr-verdict-free` (23K pairs, 112 countries) and
  `overthelex/echr-ukr-verdict-free` (2.6K, cross-family leakage-verified).
- License: CC-BY-4.0. Public HUDOC only — fully redistributable.
- Temporal methodology: arXiv:2605.24452.
