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


def test_current_sources_have_no_registry_cover_blocks():
    """Check the current canonical input instead of retired release snapshots."""
    from pathlib import Path
    rows = json.loads((Path(ROOT) / "data/processed/echr_unified.json").read_text(encoding="utf-8"))
    flagged = {row["item_id"] for row in rows if find(row["full_case_text_no_verdict"])}
    assert not flagged, sorted(flagged)
