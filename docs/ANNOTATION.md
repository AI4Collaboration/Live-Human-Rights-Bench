# Human validation of paragraph back-reference mapping

This 120-item annotation set checks whether a cited paragraph number maps to the
intended factual paragraph. The current factual-coverage experiment operates on
atomic claims; see [SUMMARIZATION_PROTOCOL.md](SUMMARIZATION_PROTOCOL.md).
The two analyses have separate units and denominators.

## Data and annotation rules

[`annotation_merged.csv`](../data/annotation/annotation_merged.csv) contains
**101 genuine pairs and 19 blind controls**. Each row includes the reasoning
paragraph, the proposed fact paragraph, the displayed paragraph number and the
judgment link. Each item appears on two of three overlapping sheets; four sheets
were returned because one sheet was completed independently by two annotators,
so 80 items carry three labels. Labels A-D are anonymous annotator identifiers.

The [instructions](annotation/INSTRUCTIONS.md) define `yes`, `no` and `unclear`.
References appearing only in a range or list require `unclear`. Of the genuine
pairs, 65 are single-pointer items, 35 refer to ranges/lists and one (P051) is a
construction error: the displayed number is absent from the reasoning.

Four controls are defective because their altered number points to a genuine
source paragraph. Four more are range cases requiring `unclear`. The remaining
**11 controls** are scoreable.

## Results by annotator

| Annotator | Mapping confirmed on genuine single-pointer items | Scoreable controls correctly rejected |
| --- | ---: | ---: |
| A | 45/47 (95.7%) | 8/9; one unclear |
| B *(excluded)* | 40/40 (100%) | 0/7 |
| C | 38/43 (88.4%) | 4/6; two unclear |
| D | 37/40 (92.5%) | 4/7 |

**Retention rule.** A sheet counts only if it rejects a majority of the
scoreable controls it contains. A, C and D do; B rejects none of its seven and
passes all of them, so **B is excluded from every reported figure**. Excluding it
costs no coverage: all 120 items retain two labels without B.

B is also the clearest reason to report control performance alongside
confirmation rates. Its 100% confirmation is the highest in the table and means
nothing on its own, because the same sheet accepted every control.

Agreement on shared genuine single-pointer items is A-C 25/25, A-D 21/22 and
C-D 16/18 among the retained sheets; the excluded sheet gives A-B 21/22,
B-C 14/18 and B-D 37/40.

The figures reported in the paper come from the retained sheets only:
confirmation of **88-96%** (A, C and D) and pairwise agreement of
**0.89-1.00** (A-C, A-D and C-D).

## Reproduce

```bash
python scripts/score_annotation.py
```

The script reads only the merged CSV. Its `cite_class` is derived from the
reasoning text; `control_status` identifies scoreable, defective and excused
controls. The merged artifact supports public verification without publishing
annotator identities or their original sheets. New annotation rounds require
new blind controls.
