# Human validation of paragraph back-reference mapping

This 120-item annotation set checks whether a cited paragraph number maps to the
intended factual paragraph. The current factual-coverage experiment operates on
atomic claims; see [SUMMARIZATION_PROTOCOL.md](SUMMARIZATION_PROTOCOL.md).
The two analyses have separate units and denominators.

## Data and annotation rules

[`annotation_merged.csv`](../data/annotation/annotation_merged.csv) contains
**101 genuine pairs and 19 blind controls**. Each row includes the reasoning
paragraph, the proposed fact paragraph, the displayed paragraph number and the
judgment link. Four annotators returned overlapping sheets; labels A-D are
anonymous identifiers.

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
| B | 40/40 (100%) | 0/7 |
| C | 38/43 (88.4%) | 4/6; two unclear |
| D | 37/40 (92.5%) | 4/7 |

Agreement on shared genuine single-pointer items is A-B 21/22, A-C 25/25,
A-D 21/22, B-C 14/18, B-D 37/40 and C-D 16/18. Report control performance
alongside confirmation rates; a high confirmation rate alone does not establish
that an annotator distinguished valid mappings from controls.

## Reproduce

```bash
python scripts/score_annotation.py
```

The script reads only the merged CSV. Its `cite_class` is derived from the
reasoning text; `control_status` identifies scoreable, defective and excused
controls. The merged artifact supports public verification without publishing
annotator identities or their original sheets. New annotation rounds require
new blind controls.
