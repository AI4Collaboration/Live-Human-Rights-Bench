"""The cut has to be the release's cut, not a plausible one of our own.

The load-bearing test is the last: stripping the pre-repair rows of `echr_unified.json`
must reproduce what the release actually contains. Everything above it guards the edges
where a cover page does not look the way the common case looks.
"""

import json
import os
import re
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "experiments"))

from headnote import find, strip   # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
COVER = ("FIRST SECTION\nCASE OF X v. Y\n(Application no. 1/11)\n\xa0\nJUDGMENT\n\xa0\n"
         "Art 8 • Correspondence • Additional limitation of the applicant's rights\n\xa0\n"
         "Prepared by the Registry. Does not bind the Court. STRASBOURG\n10 July 2025\n"
         "THE FACTS\n1. The applicant was born in 1980.")


def test_the_block_is_found_and_removed():
    assert find(COVER)
    out = strip(COVER)
    assert "•" not in out and "Prepared by the Registry" not in out
    assert "JUDGMENTSTRASBOURG" in out


def test_the_facts_are_untouched():
    assert "1. The applicant was born in 1980." in strip(COVER)


def test_a_cover_page_without_a_block_is_left_alone():
    plain = COVER.replace("Art 8 • Correspondence • Additional limitation of the applicant's rights\n\xa0\n", "")
    plain = plain.replace("Prepared by the Registry. Does not bind the Court. ", "")
    assert find(plain) is None
    assert strip(plain) == plain


def test_a_bullet_deep_in_the_body_is_not_a_cover_page_block():
    body = "JUDGMENT\nSTRASBOURG\n" + "x" * 9000 + "\nArt 8 • something • else\n"
    assert find(body) is None


def test_no_strasbourg_means_no_cut():
    assert find("JUDGMENT\nArt 8 • Correspondence • whatever\nTHE FACTS") is None


def test_empty_text_is_not_an_error():
    assert find("") is None and strip("") == ""


@pytest.mark.skipif(not os.path.isdir(os.path.join(ROOT, ".git")),
                    reason="needs the repository history")
def test_stripping_the_pre_repair_rows_reproduces_the_release():
    """Read the boundary off the release rather than inventing one."""
    field = "full_case_text_no_verdict"

    def corpus(ref):
        out = subprocess.check_output(
            ["git", "show", f"{ref}:data/processed/echr_unified.json"], cwd=ROOT)
        return {r["item_id"]: r[field] for r in json.loads(out)}

    try:
        before, after = corpus("ecb5e60"), corpus("8c43527")
    except subprocess.CalledProcessError:
        pytest.skip("pre-repair or released commit not present in this clone")
    normalise = lambda s: re.sub(r"\s+", " ", s).strip()
    rows = [i for i in before if find(before[i])]
    assert len(rows) > 100
    matched = sum(1 for i in rows
                  if normalise(strip(before[i])[:400]) == normalise(after[i][:400]))
    # The release also re-fetched some sources from HUDOC, which changes whitespace and
    # wording independently of where the block was cut; those rows are the remainder.
    assert matched / len(rows) > 0.95
