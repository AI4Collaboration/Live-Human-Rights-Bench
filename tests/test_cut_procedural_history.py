"""A cut that removes anything but the sentence it was given is a corpus rewrite.

The script edits the evaluation inputs, so what is asserted here is the boundary of the
edit: the quote goes, everything either side of it stays, a quote that is not there is
refused rather than approximated, and spans of other kinds are never touched.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "experiments"))

from cut_procedural_history import (adjudicated_extras, cuts_for,   # noqa: E402
                                    excise)
from verdict_spans import COURT_THIS_CASE, EARLIER_INSTANCE  # noqa: E402

CHAMBER = "The Chamber held that there had been no violation of Article 3."
TEXT = ("PROCEDURE\n1. The case originated in an application. " + CHAMBER +
        " 2. The applicant was born in 1955.\n\nTHE FACTS\n3. On 20 April 1998 ...")


def row(item_id="001-1", text=TEXT):
    return {"item_id": item_id, "article": "3", "full_case_text_no_verdict": text}


def audit_row(quote, category=EARLIER_INSTANCE, tier="leak", item_id="001-1"):
    return {"item_id": item_id, "article": "3", "case_name": "CASE OF X v. Y",
            "violation_label": "violation",
            "spans": [{"quote": quote, "category": category, "tier": tier}]}


def test_the_sentence_goes_and_the_rest_stays():
    out = excise(TEXT, CHAMBER)
    assert CHAMBER not in out
    assert "The case originated in an application." in out
    assert "2. The applicant was born in 1955." in out
    assert "THE FACTS" in out


def test_the_join_does_not_announce_itself():
    assert "  " not in excise(TEXT, CHAMBER)


def test_a_quote_that_is_not_there_is_refused_rather_than_approximated():
    assert excise(TEXT, "The Chamber held that there had been a violation of Article 8.") is None


def test_only_earlier_instance_leaks_are_cut():
    rows = [row()]
    assert cuts_for(rows, [audit_row(CHAMBER)]) == {"001-1": [CHAMBER]}
    assert cuts_for(rows, [audit_row(CHAMBER, category=COURT_THIS_CASE)]) == {}
    assert cuts_for(rows, [audit_row(CHAMBER, tier="review")]) == {}


def test_a_span_the_repair_already_removed_is_not_this_scripts_business():
    """The audit ran on the pre-repair text, so some of its quotes are simply gone."""
    rows = [row(text="PROCEDURE\n1. The case originated in an application.")]
    assert cuts_for(rows, [audit_row(CHAMBER)]) == {}


def test_one_text_per_judgment_however_many_articles_are_scored_from_it():
    """Two instances share a judgment; the quote must be listed once, not twice."""
    rows = [row(), {**row(), "article": "6"}]
    found = cuts_for(rows, [audit_row(CHAMBER), {**audit_row(CHAMBER), "article": "6"}])
    assert found == {"001-1": [CHAMBER]}


def test_a_readers_upgrade_is_cut_even_though_no_category_rule_finds_it(tmp_path):
    """001-229927: admissibility wording that states the outcome for the scored Article."""
    path = tmp_path / "adjudication.json"
    path.write_text(json.dumps({"review_tier_upgraded": [
        {"item_id": "001-9", "article": "34", "verdict": "leak", "quote": CHAMBER},
        {"item_id": "001-9", "article": "38", "verdict": "leak", "quote": CHAMBER},
        {"item_id": "001-9", "article": "5", "verdict": "harmless", "quote": "ignored"},
    ]}))
    assert adjudicated_extras(str(path)) == {"001-9": [CHAMBER]}


def test_no_adjudication_file_is_not_an_error():
    assert adjudicated_extras("/nonexistent/adjudication.json") == {}
