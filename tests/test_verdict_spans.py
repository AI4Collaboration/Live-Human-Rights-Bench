"""The detector has to be verified before its output is read as a leak rate.

Every assertion here is a failure mode that a plain string comparison has, and that a
count built on one would inherit silently: real HUDOC punctuation rejected as invented,
invented sentences accepted as found, a reply that parses to nothing counted as a clean
case. The corpus test at the end runs against the shipped dataset rather than a fixture,
because the punctuation traps are properties of HUDOC and not of anything written here.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "experiments"))

from verdict_spans import (ADMISSIBILITY_ONLY, CATEGORIES,                 # noqa: E402
                           COURT_THIS_CASE, OTHER_AUTHORITY, PARTY_POSITION,
                           SPAN_TEMPLATE, UNLABELLED, locate, parse_spans,
                           prompt_digest, tier_of, verify)

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SOURCE = ("35. The applicant complained under Article 3.\n\n36. Accordingly, there has "
          "been a violation of Article 3 of the Convention.")


def test_locate_returns_the_real_offsets():
    quote = "Accordingly, there has been a violation of Article 3 of the Convention."
    start, end = locate(quote, SOURCE)
    assert SOURCE[start:end] == quote


def test_quote_retyped_across_a_line_break_is_still_verbatim():
    source = "36. Accordingly, there has been\na violation of Article 3."
    assert locate("Accordingly, there has been a violation of Article 3.", source)


def test_hudoc_punctuation_survives_the_round_trip():
    # Non-breaking spaces and curly quotes are what HUDOC actually ships; a model
    # retyping the sentence emits ordinary ones, and a raw comparison would call the
    # correct quote invented.
    source = "The Court’s assessment: there has been a violation of Article 5."
    assert locate("The Court's assessment: there has been a violation of Article 5.", source)


def test_a_sentence_that_is_not_in_the_source_is_not_located():
    assert locate("The Court finds a violation of Article 8.", SOURCE) is None


def test_verify_drops_invented_quotes_and_keeps_the_rest():
    spans = [{"quote": "Accordingly, there has been a violation of Article 3 of the Convention.",
              "category": COURT_THIS_CASE},
             {"quote": "The Court finds a violation of Article 8.", "category": COURT_THIS_CASE}]
    kept, dropped = verify(spans, SOURCE)
    assert len(kept) == 1 and len(dropped) == 1
    assert SOURCE[kept[0]["start"]:kept[0]["end"]] == kept[0]["quote"]
    assert kept[0]["tier"] == "leak"


def test_empty_array_is_an_answer_not_a_parse_failure():
    assert parse_spans("[]") == []


def test_fenced_and_wrapped_replies_both_parse():
    item = {"quote": "x", "category": COURT_THIS_CASE}
    assert parse_spans("```json\n" + json.dumps([item]) + "\n```") == [item]
    assert parse_spans(json.dumps({"spans": [item]})) == [item]


def test_an_unknown_category_is_flagged_rather_than_guessed():
    spans = parse_spans(json.dumps([{"quote": "x", "category": "probably_a_leak"}]))
    assert spans[0]["category"] == UNLABELLED


def test_tiers_do_not_pool_a_party_position_with_the_courts_own_finding():
    party = verify([{"quote": "35. The applicant complained under Article 3.",
                     "category": PARTY_POSITION}], SOURCE)[0]
    assert tier_of(party) == "review"
    assert tier_of([]) == "clean"


def test_admissibility_is_not_scored_as_a_finding_on_the_merits():
    """The first run had no such class and scored these as the Court's verdict."""
    source = ("It follows that this part of the application is manifestly ill-founded "
              "and must be rejected in accordance with Article 35 §§ 3 (a) and 4.")
    kept, _ = verify([{"quote": source, "category": ADMISSIBILITY_ONLY}], source)
    assert kept[0]["tier"] == "review"
    assert tier_of(kept) != "leak"


def test_a_changed_prompt_changes_the_checkpoint_identity():
    """Rows answering an earlier question must not be resumed under a new one."""
    import verdict_spans

    before = prompt_digest()
    original = verdict_spans.SPAN_TEMPLATE
    try:
        verdict_spans.SPAN_TEMPLATE = original + "\nOne more rule."
        assert prompt_digest() != before
    finally:
        verdict_spans.SPAN_TEMPLATE = original
    assert prompt_digest() == before


def test_prompt_names_the_article_and_every_category():
    filled = SPAN_TEMPLATE.format(case_name="CASE OF X v. Y", article="6", text="...")
    assert filled.count("Article 6") >= 3
    for category in CATEGORIES:
        assert category in filled
    assert OTHER_AUTHORITY in filled


@pytest.mark.skipif(not os.path.exists(os.path.join(ROOT, "data/processed/echr_unified.json")),
                    reason="evaluation pool not present")
def test_real_sentences_from_the_pool_are_locatable_after_normalisation():
    """A quote is only evidence if it can be found in the text the runner sends."""
    rows = json.load(open(os.path.join(ROOT, "data/processed/echr_unified.json")))
    checked = 0
    for row in rows[:40]:
        text = row.get("full_case_text_no_verdict") or ""
        for line in text.split("\n"):
            line = line.strip()
            if len(line) < 120:
                continue
            # What a model gives back: whitespace collapsed, punctuation normalised.
            retyped = " ".join(line.split()).replace("’", "'").replace("“", '"')
            span = locate(retyped, text)
            assert span is not None, f"{row['item_id']}: {retyped[:60]}"
            checked += 1
            break
    assert checked >= 20
