"""Reviewable ECtHR facts/assessment boundaries, including flattened documents.

Only structural headers trigger automatic truncation. Domestic-court findings,
prior-case citations, and generic uses of 'assessment' are not truncation rules.
Offsets always address the original string; no generated text is substituted.
"""

import re

LAW = re.compile(r"\b(?:AS TO )?THE LAW(?!YER|FUL|LESS)(?!\s+(?:OF|ON|No\.)\b)")
FACTS = re.compile(r"\bTHE FACTS\b(?!\s+(?:LEADING|SUBSEQUENT)\b)")
ASSESSMENT = re.compile(
    r"THE COURT['’]S (?:ASSESSMENT|EVALUATION)|"
    r"The Court['’]s (?:assessment|evaluation)(?!\s*(?:of\b|will\b|,|\.))"
)
TOC = re.compile(r"\bTABLE OF CONTENTS\b", re.I)


def repair(text):
    """Return (unchanged factual prefix, evidence for every removed span).

    The first body LAW header wins, not the last occurrence in a quoted law.
    Where an ECtHR document has no LAW header, use a genuine assessment heading.
    A TOC must have a later body introduction before it is removed.
    """
    spans = []
    # Official cover-page headnotes summarize the current judgment's reasoning.
    # Keep the document identity, but not the Art ... bullet synopsis.
    title = re.search(r"\bJUDGMENT", text)
    city = re.search(r"\bSTRASBOURG", text)
    if title and city and title.end() < city.start():
        cover = text[title.end():city.start()]
        if re.search(r"\bArt(?:icle)?\.?\s+\d", cover):
            spans.append({"start": title.end(), "end": city.start(), "reason": "judgment_headnote"})
    toc = TOC.search(text)
    body_anchor = re.search(r"\bIn the case of\b", text)
    body_start = body_anchor.start() if body_anchor else 0
    if toc:
        body = re.search(r"\bIn the case of\b", text[toc.end():])
        if body:
            body_start = toc.end() + body.start()
            spans.append({"start": toc.start(), "end": body_start,
                          "reason": "table_of_contents"})
        else:
            raise ValueError("Table of contents without an unambiguous body start")
    elif body_anchor:
        # Older documents can carry an unlabelled contents list.
        early_facts = FACTS.search(text[:body_start])
        if early_facts:
            starts = [m.start() for m in re.finditer(r"\bPROCEDURE\b|\bTHE FACTS\b", text[:body_start])]
            spans.append({"start": min(starts), "end": body_start,
                          "reason": "unlabelled_table_of_contents"})
    facts = [m for m in FACTS.finditer(text) if m.start() >= body_start]
    factual_start = facts[0].end() if facts else body_start
    laws = [m for m in LAW.finditer(text) if m.start() >= factual_start]
    assessments = [m for m in ASSESSMENT.finditer(text) if m.start() >= factual_start]
    candidates = [(m.start(), "law_section") for m in laws]
    candidates += [(m.start(), "court_assessment_section") for m in assessments]
    if candidates:
        cutoff, reason = min(candidates)
        spans.append({"start": cutoff, "end": len(text), "reason": reason})
    if not spans:
        return text, []
    parts, cursor = [], 0
    for span in sorted(spans, key=lambda s: s["start"]):
        if span["start"] < cursor:
            raise ValueError("Overlapping source-removal spans")
        parts.append(text[cursor:span["start"]])
        cursor = span["end"]
    parts.append(text[cursor:])
    clean = "".join(parts).rstrip()
    if not clean.strip():
        raise ValueError("Repair would empty a source")
    for span in spans:
        span["boundary_context"] = text[max(0, span["start"]-180):span["start"]+300]
    return clean, spans
