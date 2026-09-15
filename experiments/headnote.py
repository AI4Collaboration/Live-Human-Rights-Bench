"""The Registry keyword line, and where the 15 September repair cut it.

Modern HUDOC judgments carry a Registry summary on the cover page, between the word
JUDGMENT and the place of delivery:

    JUDGMENT
    Art 8 • Correspondence • Additional limitation of applicant's right to correspondence
    during special regime detention • Lack of any explicit reference to specific
    circumstances justifying the impugned measure ...
    Prepared by the Registry. Does not bind the Court.
    STRASBOURG

It states the outcome in one line, above the facts, which is why 251 of the 1,000
instances in the unified pool flagged as leaks before the repair removed it. Two other
corpora were built from the same HUDOC sources and never went through that repair:
`echr-livehrb-stateswap` carries it on 186 of 816 scored texts, `echr-livehrb-static-2k`
on 310 of 2,000.

The boundary here is not invented: it is read off the released corpus. The repair cuts
from the end of JUDGMENT to the start of STRASBOURG and joins them directly, which is why
the repaired texts read "JUDGMENTSTRASBOURG". `reproduces_release` in the tests asserts
that this function returns exactly what the release contains, on the release's own rows.

Nothing is cut unless the span between the anchors actually carries the block, so a cover
page that runs JUDGMENT straight into STRASBOURG is left alone rather than rewritten.
"""

import re

JUDGMENT = re.compile(r"JUDGMENT")
STRASBOURG = re.compile(r"STRASBOURG")
# A keyword line is bulleted; the standalone disclaimer appears on its own in some
# judgments and is part of the same Registry block.
BLOCK = re.compile(r"•|Prepared by the Registry")

HEAD_WINDOW = 6_000      # the cover page; the word JUDGMENT recurs in the body
SPAN_LIMIT = 8_000       # a keyword block is long, but not that long


def find(text):
    """Character span of the Registry block, or None when there is not one."""
    if not text:
        return None
    start = JUDGMENT.search(text, 0, HEAD_WINDOW)
    if not start:
        return None
    end = STRASBOURG.search(text, start.end(), start.end() + SPAN_LIMIT)
    if not end:
        return None
    between = text[start.end():end.start()]
    if not BLOCK.search(between):
        return None
    return start.end(), end.start()


def strip(text):
    """Text with the Registry block removed, joined as the release joins it."""
    span = find(text)
    if span is None:
        return text
    return text[:span[0]] + text[span[1]:]
