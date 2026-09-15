"""Do not reproduce the linebreak, short-document, TOC, or domestic-law bugs."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from leak_audit.boundaries import repair


def test_inline_short_law_section():
    text = "THE FACTS 1. Domestic remedies were exhausted. THE LAW\nThe Court found a violation."
    clean, spans = repair(text)
    assert clean == "THE FACTS 1. Domestic remedies were exhausted."
    assert spans[0]["reason"] == "law_section"


def test_domestic_law_titles_are_retained():
    text = "THE FACTS 1. Relevant legislation. THE LAW OF 2002 ON EUTHANASIA 2. Section 4. THE LAW 3. Admissibility."
    clean, _ = repair(text)
    assert clean.endswith("THE LAW OF 2002 ON EUTHANASIA 2. Section 4.")


def test_domestic_assessment_prose_is_retained():
    for text in ["In the court’s assessment, her testimony was unreliable.",
                 "This may form part of the Court’s assessment in deciding the appeal."]:
        assert repair(text) == (text, [])


def test_flattened_assessment_heading():
    text = "The applicant exhausted domestic remedies.THE COURT’S ASSESSMENTAdmissibility1. The Court notes a violation."
    assert repair(text)[0] == "The applicant exhausted domestic remedies."


def test_toc_does_not_cut_the_facts():
    text = "Title TABLE OF CONTENTS THE FACTS THE LAW The Court’s assessment APPENDIX In the case of X. THE FACTS 1. Event. THE LAW 2. Finding."
    clean, spans = repair(text)
    assert clean == "Title In the case of X. THE FACTS 1. Event."
    assert len(spans) == 2


def test_earlier_outcome_is_not_a_cut_marker():
    text = "THE FACTS 1. In an earlier judgment the Court found a violation. 2. The domestic court later heard the appeal."
    assert repair(text) == (text, [])


def test_flattened_headnote_with_black_circle_is_removed():
    text = "CASE OF X JUDGMENTArt 6 ● Fair hearing ● No violation STRASBOURG 2020 THE FACTS 1. The hearing took place."
    clean, spans = repair(text)
    assert "No violation" not in clean
    assert "The hearing took place." in clean
    assert spans[0]["reason"] == "judgment_headnote"


def test_contiguous_numbered_law_heading_is_removed():
    clean, _ = repair("THE FACTS1. The applicant appealed.THE LAW14. The Court finds a violation.")
    assert "The applicant appealed." in clean
    assert "finds a violation" not in clean


def test_unlabelled_toc_does_not_remove_body_facts():
    text = "Title PROCEDURE 1 THE FACTS 2 THE LAW 5 In the case of X THE FACTS 1. An appeal was filed. THE LAW 2. Merits."
    clean, _ = repair(text)
    assert clean == "Title In the case of X THE FACTS 1. An appeal was filed."


def test_appendix_excludes_current_award_but_preserves_domestic_history():
    from leak_audit.factual_tables import extract
    html = """<table><tr><td>Application no.</td><td>Conditions of detention</td>
    <td>Domestic award</td><td>Amount awarded for non-pecuniary damage</td></tr>
    <tr><td>123/20</td><td>2.6 square metres for 27 days</td><td>500 euros ordered by the domestic court</td>
    <td>5,000 euros</td></tr><tr><td>456/20</td><td>unrelated applicant facts</td><td>1</td><td>2</td></tr></table>"""
    text, included, excluded = extract(html, "123/20")
    assert "2.6 square metres for 27 days" in text
    assert "500 euros ordered by the domestic court" in text
    assert "5,000 euros" not in text
    assert "unrelated applicant facts" not in text
    assert "Domestic award" in included
    assert "Amount awarded for non-pecuniary damage" in excluded


def test_unknown_appendix_header_requires_review():
    import pytest
    from leak_audit.factual_tables import extract
    html = "<table><tr><td>Application no.</td><td>Unknown conclusion field</td></tr><tr><td>123/20</td><td>x</td></tr></table>"
    with pytest.raises(ValueError, match="Unreviewed appendix headers"):
        extract(html, "123/20")
