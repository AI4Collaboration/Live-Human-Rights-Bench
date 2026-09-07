# Human validation of the back-reference mapping

Materiality in this project is not judged by an annotator. It is read off the Court`s own
back-references: when a judgment writes "see paragraph 18 above", the Court has itself said
that paragraph 18 is a fact its reasoning rests on. That construction is what this exercise
validates, so annotators only check a mapping and never decide what mattered.

## The set

120 items, `data/annotation/annotation_merged.csv`, self-contained: each row carries the
reasoning paragraph, the fact paragraph our tool believes it points at, the shown paragraph
number and a link to the judgment.

* **101 genuine** back-reference pairs and **19 blind controls** whose paragraph number was
  altered on purpose, so the correct answer on a control is `no`.
* Three sheets of 80 rows, every pair of sheets sharing 40 items, so each item was labelled
  independently by two people. Four annotators returned sheets; one sheet was covered twice.
* Labels are `yes`, `no` or `unclear`, one column per annotator as `label_A` to `label_D`.
  The letters are stable; the mapping to people is held privately.

## Reading the derived columns

* `cite_class` — whether the reasoning cites the shown number on its own, only inside a
  range or list, or never. It is computed from the reasoning text, not from the key.
* `control_status` — `scoreable`, `defective` or `excused`, see below.
* `pointer_kind`, `sheets`, `expected`, `accepts_unclear` come from the build.

## Two caveats that change the arithmetic

**Four controls are defective** (P014, P073, P095, P053). The renumbering landed on a
paragraph that genuinely is a source, so `yes` is the correct answer and the key is wrong.
Three of them were caught by annotators disagreeing with the key, not by us.

**Four more cannot be scored** (P036, P084, P090, P099): the number appears only inside a
cited range, and the written instructions tell the annotator to answer `unclear` in exactly
that situation, so a `no` cannot be demanded.

That leaves **11 controls that test anything**, and only those are scored.

## What the exercise found

* On the 65 genuine single-pointer items, the subset the protocol can validate, the mapping
  is confirmed on **88 to 96 percent** of items depending on the annotator.
* Pairwise agreement on that subset runs from 0.89 to 1.00 among the annotators whose sheets
  passed the control check.
* **P051 is a genuine construction error**, one in 101: the shown number is never cited
  anywhere in the reasoning. It is dropped from the validation set and reported as such.
* Thirty-five of the 101 genuine items point at a range or a list rather than a single
  paragraph. Those are `unclear` by protocol, and that is the honest answer rather than a
  convention: where the Court cites several paragraphs its reliance is distributed across
  them, so asking whether one of them is "the source" is ill-posed.

## Reproducing the figures

    python scripts/score_annotation.py

It reads `data/annotation/annotation_merged.csv` and nothing else. If a number in the paper
disagrees with its output, the paper is wrong.

## What is deliberately not here

Annotator identities, and the raw per-annotator sheets as returned. Committing the merged
table does disclose which rows are controls, which is intentional: the control figures are
reported in the paper and a reader cannot check them otherwise. It does mean these particular
controls are spent, and a future refresh of the sets needs freshly built ones.
