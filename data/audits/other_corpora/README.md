# The two corpora the 15 September repair never touched

`echr_unified.json` was repaired and re-released. The state-swap arm and the MFT arm score
different corpora, built from the same HUDOC sources and never put through it:

| corpus | scored field | rows audited |
|---|---|---|
| `overthelex/echr-livehrb-stateswap` | `case_text_rendered` | 816 base texts, one per case-article group |
| `overthelex/echr-livehrb-static-2k` | `verdict_free_text` | 2,000, the source the MFT paragraphs are generated from |

## What the detector found, and what the strip fixed

| corpus | leak before | after the Registry line was stripped | rows cut |
|---|---|---|---|
| state-swap | 458 of 816 (56%) | **286 (35%)** | 183, 132,260 characters |
| static-2k | 1,143 of 2,000 (57%) | **884 (44%)** | 311, 245,538 characters |

On the rows that carried it, the keyword line was doing nearly all of the work: state-swap
177 leaking of 183 before and 5 after, static-2k 286 of 311 before and 27 after. Both
corpora are structurally clean under `leak_audit/leakdef.py`, which is exactly why this
went unnoticed: the Court's law section is gone and the telegraphic summary of the outcome
above the facts is not.

## What is not fixed

The residue is the Court's own reasoning left inside the facts, 286 rows and 884 rows.
No deterministic cut reaches it; it needs the source repair the 15 September release ran.

## Files

- `*_spans_before.json` - the full detector pass over each corpus.
- `*_spans_after_strip.json` - the same detector over only the rows whose Registry line was
  removed, which is what the second column above is measured from.
- `*_headnote_strip.json` - what `scripts/strip_registry_headnote.py` removed, per row.

The repaired corpora themselves are not here: they live on the Hub, and republishing them
is a release decision rather than a commit. State-swap also needs the cut applied to all
3,264 rows rather than the 816 audited here, and to `case_text_templated` beside
`case_text_rendered`, since a stale column has already been left next to a clean one once.
