"""Re-cut the stale placeholder column in the published state-swap set.

`case_text_rendered`, the field the models are actually scored on, was corrected on
26 August and audits clean on all 3,264 rows. `case_text_templated`, the intermediate
column carrying the [DEFENDANT STATE] placeholders, was left as it was and still held
the Court`s assessment on 588 of them. Nothing reads that column, but shipping a
leaking one beside a clean one is how a later run picks the wrong field, so it gets
the same cut. The 17.9% quoted in an early draft of Section 3 came from this column,
not from the scored one.

    python scripts/recut_stateswap.py --out build/stateswap_templated_recut.parquet

Membership, row order and every other column are asserted unchanged, so the published
numbers stay comparable and a diff shows exactly the repair.
"""
import argparse, os, sys

import datasets

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "leak_audit"))
from leakdef import leaking, recut  # noqa: E402

FIELD = "case_text_templated"
DATASET = "overthelex/echr-livehrb-stateswap"


def main(dataset, out):
    df = datasets.load_dataset(dataset)["train"].to_pandas()
    before = [bool(leaking(t or "")) for t in df[FIELD]]
    print("published rows: %d, %s leaking: %d" % (len(df), FIELD, sum(before)))

    fixed = df.copy()
    fixed[FIELD] = [recut(t) if f else t for t, f in zip(df[FIELD], before)]

    assert not any(leaking(t or "") for t in fixed[FIELD]), "a row is still flagged"
    assert len(fixed) == len(df), "row count changed"
    assert list(fixed["swap_group_id"]) == list(df["swap_group_id"]), "membership changed"
    for column in df.columns:
        if column != FIELD:
            assert fixed[column].equals(df[column]), "column %s changed" % column
    print("row order, membership and every other column verified identical")

    # Once the placeholders are filled the two columns describe the same judgment, so a
    # ratio far from 1 means the cut landed differently on the two and wants looking at.
    ratio = fixed["case_text_rendered"].str.len() / fixed[FIELD].str.len()
    print("rendered/templated length ratio: median %.2f  min %.2f  max %.2f"
          % (ratio.median(), ratio.min(), ratio.max()))

    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    fixed.to_parquet(out, index=False)
    print("wrote %s" % out)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--dataset", default=DATASET)
    p.add_argument("--out", default="build/stateswap_templated_recut.parquet")
    main(**vars(p.parse_args()))
