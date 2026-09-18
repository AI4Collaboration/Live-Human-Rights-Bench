# Historical audits of deprecated source corpora

Status clarified **18 September 2026**. The legacy State Swap and static-2k
releases are **deprecated as evaluation inputs**. Exact Hub versions, replacements
and pending artifacts are listed in the
[source-status register](../../../docs/DATA_SOURCE_STATUS.md).

The September main-input repair applied to `echr_unified.json`. These audit
files describe separate local exports of older corpora; their detection results
do not describe the current 1,000-target input or an updated State Swap run.

| Historical corpus | Original field | Audit unit |
| --- | --- | --- |
| `overthelex/echr-livehrb-stateswap` | `case_text_rendered` | 816 case-article base texts, one per swap group |
| `overthelex/echr-livehrb-static-2k` | `verdict_free_text` | 2,000 source rows used by earlier MFT generation |

## Detector results and the local headnote strip

The audit status is **`CANDIDATES_WITH_EVIDENCE_NOT_AN_ADJUDICATED_RATE`**.
The `leak` tier records detector candidates with located quotes. These counts
are not fully adjudicated leakage rates.

| Corpus | `leak` flags before | Rows stripped and rechecked | `leak` flags in that subset, before / after | Flags remaining across the full old corpus |
| --- | ---: | ---: | ---: | ---: |
| State Swap | 458 / 816 | 183 | 177 / 5 | **458 - 177 + 5 = 286 / 816** |
| static-2k | 1,143 / 2,000 | 311 | 286 / 27 | **1,143 - 286 + 27 = 884 / 2,000** |

The local strip removed 132,260 and 245,538 characters, respectively. Only the
modified subset was rechecked. The old structural detector reported both
corpora clean, demonstrating that its boundary checks did not cover every
answer-bearing headnote or inline passage.

Earlier wording described all remaining flags as the Court's reasoning inside
the facts. The files establish candidate flags, which require attribution to
the judgment being predicted. Earlier decisions and procedural history do not
by themselves reveal that judgment's final answer.

## Provenance and publication status

- `*_spans_before.json`: complete detector pass, including the local input's
  `dataset_sha256_lf`.
- `*_spans_after_strip.json`: detector pass over only the modified rows, with
  the post-strip input hash.
- `*_headnote_strip.json`: local cuts, row identities and pre-strip file hash.

These records document local stripping. They do not establish that a repaired
replacement was published to the Hub. The audited export hashes and the Hub
heads observed on 18 September are recorded separately in
[`configs/data_source_status.json`](../../../configs/data_source_status.json);
these records do not establish an exact export-to-Hub-revision binding.

The updated `data/processed/echr_stateswap.json` is absent from the inspected
GitHub revision. Publish the actual new input and its review evidence with the
new results. A State Swap repair must cover all distributed arms and both
`case_text_rendered` and `case_text_templated` when both fields are present.
The old 286 / 816 count cannot be assigned to that new run.
