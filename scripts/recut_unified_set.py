"""Re-cut the unified evaluation set so no row carries the Court`s legal assessment.

Membership is never touched: the corrected text is joined onto the existing rows, so
every figure computed before and after stays comparable. Only `full_case_text_no_verdict`
changes, and only on rows the canonical detector flags.

    python scripts/recut_unified_set.py data/processed/echr_unified.json
"""
import json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "leak_audit"))
from leakdef import leaking, recut  # noqa: E402

FIELD = "full_case_text_no_verdict"


def main(path):
    rows = json.load(open(path, encoding="utf-8"))
    flagged = [i for i, r in enumerate(rows) if leaking(r[FIELD] or "")]
    for i in flagged:
        rows[i] = {**rows[i], FIELD: recut(rows[i][FIELD])}

    still = [i for i in flagged if leaking(rows[i][FIELD])]
    assert not still, "rows still flagged after the re-cut: %s" % still[:5]
    assert all(rows[i][FIELD] for i in flagged), "the re-cut emptied a row"

    json.dump(rows, open(path, "w", encoding="utf-8"), ensure_ascii=False)
    print("re-cut %d of %d rows; membership unchanged" % (len(flagged), len(rows)))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/processed/echr_unified.json")
