"""Locate Registry cover headnotes before the judgment's case record.

This boundary detector identifies the cover block between JUDGMENT and
STRASBOURG. Its result is a structural candidate, not a semantic leakage verdict.
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
