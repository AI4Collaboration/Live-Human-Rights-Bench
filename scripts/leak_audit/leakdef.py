"""Structural screen and boundary cut for retained court-reasoning sections.

The screen detects a THE LAW section followed by an assessment or merits heading.
Repeated headings in a table of contents are handled by preferring later section
boundaries. The cut preserves the facts section before the reasoning boundary.

Source review also checks answer-revealing passages within retained facts, with
attribution to the judgment being predicted. See docs/INPUT_REPAIR.md for the
current review scope. This module supplies the structural component.
"""

import re

LAW = re.compile(r"(?:^|\n)\s*(?:[IVX]+\.\s*)?THE LAW\s*(?:\n|$)", re.I | re.M)
FACTS = re.compile(r"(?:^|\n)\s*(?:[IVX]+\.\s*)?THE FACTS\s*(?:\n|$)", re.I | re.M)
ASSESSMENT = re.compile(
    r"The Court.s assessment|The Court.s evaluation|"
    r"Application of (?:the|these) principles|Merits",
    re.I,
)

TOC_ZONE = 12_000   # headings repeated in a table of contents live near the top
MIN_TAIL = 5_000    # shorter remainders are section stubs, not retained reasoning


def _law_positions(text, use_end=False):
    """Positions of the THE LAW header, with table-of-contents hits dropped."""
    positions = [(m.end() if use_end else m.start()) for m in LAW.finditer(text)]
    if len(positions) > 1:
        later = [p for p in positions if p > TOC_ZONE]
        if later:
            positions = later
    return positions


def leaking(text):
    """True when the Court's law section survived verdict removal."""
    positions = _law_positions(text, use_end=True)
    if not positions:
        return False
    tail = text[max(positions):]
    return len(tail) > MIN_TAIL and bool(ASSESSMENT.search(tail))


def recut(text):
    """Truncate at the structural facts/law boundary, leaving the facts intact."""
    positions = _law_positions(text)
    if not positions:
        return text
    facts = [m.start() for m in FACTS.finditer(text)]
    if facts:
        positions = [p for p in positions if p > max(facts)] or positions
    return text[:max(positions)].rstrip()
