"""Extractive summaries: verbatim paragraphs selected from the source.

The abstractive arm cannot separate two explanations for its own effect. A drop in
accuracy under summarisation may mean the summary lost something material, or it may
mean the summariser introduced something wrong. Yu Fan's objection on 25 Aug was
exactly this, and the answer we promised was an extractive control.

Here the summariser may only *choose* paragraphs, never write them. Hallucination is
impossible by construction, so any effect is attributable to omission alone -- and the
omission is not judged by a model, it is the exact set of paragraphs left out.

ECtHR judgments supply natural source boundaries. The selector keeps every passage
it judges materially necessary, with no target length or maximum length.
"""

import json
import re

SELECTION_SCHEMA = "verbatim-source-spans-v4-all-complaints-unbounded"
SPAN_SELECT_TEMPLATE = """Produce a complete extractive factual summary of this ECtHR case.

Case: {case_name}

{numbered}

Select every passage containing facts materially relevant to assessing any alleged
Convention violation in the case. This includes concrete events and conditions, dates, durations,
measurements, relevant domestic proceedings and decisions, the parties' conduct or
arguments, and relevant rows of factual tables. A sentence that merely names a
complaint is not a substitute for the underlying facts. Exclude boilerplate,
unrelated material, and legal background that does not add a case-specific fact.

There is no target length or maximum length. Return only a JSON array of passage IDs,
for example [2, 5, 8]. Do not write or paraphrase any text."""


def source_units(text):
    """Partition every source into indexed verbatim spans without relying on
    unique official paragraph numbers. Flattened text and factual tables use the
    same rule. IDs are source-order indices, not claimed ECtHR paragraph numbers.
    Every non-whitespace character belongs to exactly one unit.
    """
    starts = {0, len(text)}
    # Blank lines, line-start numbered passages, and inline numbered paragraphs.
    for pattern in (r"\n\s*\n", r"(?m)^[^\S\n]*\d{1,3}\.[^\S\n]+",
                    r"(?<![\w/])\d{1,3}\.[^\S\n]+(?=[A-Z\u201c(])"):
        starts.update(m.start() for m in re.finditer(pattern, text))
    # Keep long flattened passages selectable without rewriting a word. Sentence
    # boundaries are merely selection boundaries, not factual or legal labels.
    coarse = sorted(starts)
    for left, right in zip(coarse, coarse[1:]):
        if len(text[left:right].split()) > 180:
            starts.update(left + m.end() for m in re.finditer(r"[.!?][\"’”']?\s+(?=[A-Z\u201c(])", text[left:right]))
    units = []
    ordered = sorted(starts)
    for left, right in zip(ordered, ordered[1:]):
        while left < right and text[left].isspace():
            left += 1
        while right > left and text[right - 1].isspace():
            right -= 1
        if left < right:
            units.append({"id": str(len(units) + 1), "start": left, "end": right,
                          "text": text[left:right]})
    return units


def assemble_units(units, selected):
    selected = set(selected)
    return "\n\n".join(u["text"] for u in units if u["id"] in selected)


def selection_record(units, selected):
    selected = set(selected)
    return {"selected_units": [u["id"] for u in units if u["id"] in selected],
            "omitted_units": [u["id"] for u in units if u["id"] not in selected],
            "selected_spans": [{k:u[k] for k in ("id", "start", "end")}
                               for u in units if u["id"] in selected],
            "selected_words": sum(len(u["text"].split()) for u in units
                                  if u["id"] in selected)}

# HUDOC separates the paragraph number from its text with non-breaking spaces, not
# ordinary ones, so [ \t] matches nothing on real judgments. [^\S\n] is "whitespace
# that is not a newline", which covers \xa0 without letting the match span lines.
PARA = re.compile(r"(?m)^[^\S\n]*(\d{1,3})\.[^\S\n]+")

def split_paragraphs(text):
    """Return [(number, text)] for the numbered paragraphs of a judgment."""
    marks = [(m.group(1), m.start()) for m in PARA.finditer(text)]
    out = []
    for i, (num, start) in enumerate(marks):
        end = marks[i + 1][1] if i + 1 < len(marks) else len(text)
        body = text[start:end].strip()
        if body:
            out.append((num, body))
    return out


def parse_selection(reply, valid):
    """Pull the chosen paragraph numbers out of a model reply.

    Fenced JSON is stripped before parsing rather than salvaged afterwards: a
    salvage that cuts back to the last complete element silently drops the final
    item of every batch, which cost a rerun once.
    """
    if not reply or reply.startswith("ERROR:"):
        return []
    body = re.sub(r"^\s*```[a-z]*\s*|\s*```\s*$", "", reply.strip())
    lo, hi = body.find("["), body.rfind("]")
    picked = []
    if lo != -1 and hi > lo:
        try:
            picked = json.loads(body[lo:hi + 1])
        except json.JSONDecodeError:
            picked = []
    if not picked:                      # a bare list of numbers is common enough
        picked = re.findall(r"\d+", body)
    seen, out = set(), []
    for p in picked:
        s = str(p).strip()
        if s in valid and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def assemble(paragraphs, chosen):
    """Rebuild the extract, verbatim and in source order."""
    by_num = dict(paragraphs)
    order = [n for n, _ in paragraphs]
    return "\n\n".join(by_num[n] for n in order if n in set(chosen))


def is_verbatim(extract, source):
    """Every paragraph of the extract must appear in the source unchanged.

    This is the guarantee the arm rests on. A summariser that paraphrases while
    claiming to quote would put us back where we started, with hallucination and
    omission confounded.
    """
    if not extract:
        return False
    return all(part.strip() in source for part in extract.split("\n\n") if part.strip())


def omitted(paragraphs, chosen):
    """The exact paragraph numbers left out -- omission, counted rather than judged."""
    keep = set(chosen)
    return [n for n, _ in paragraphs if n not in keep]
