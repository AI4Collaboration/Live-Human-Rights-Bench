"""Verdict leakage as quoted evidence rather than as a regex count.

The structural leak is settled: `scripts/leak_audit/leakdef.py` defines it, the 7 Sep
re-cut repaired against it, and no judgment in the 1,000-instance pool still carries
the Court's law section. What survives is a different failure: a sentence inside the
facts that states how this Court resolved this complaint.

A lexical screen cannot be the instrument for that, and `leakdef`'s own docstring says
why -- it fires on domestic courts quoted in the facts and misses the Court's own
conclusion when it is phrased as "did not fail to fulfil its positive obligations". A
strict hand-written screen over the current pool flags 70 judgments, and reading ten of
them, four are this case's finding, one is a Government concession, and the rest are
party submissions or earlier cases. A number built that way cannot be defended.

So the model here may only *quote*. Every span it returns is located in the source
before it is counted, exactly as the extractive arm verifies its selections, which
makes invention impossible by construction and leaves a reader able to check any
positive in the output by eye. What the model supplies is attribution -- whose finding
this is -- which is the part a pattern cannot do. The rate itself comes later, from
human adjudication of a stratified sample against these spans.

Scope: prompt-level leakage in the text the runner actually sends, which is the first
`MAX_CASE_CHARS` characters. 154 of the 947 judgments are longer than that, so auditing
the stored text would measure something the models never saw. This says nothing about
pretraining contamination.
"""

import hashlib
import json
import re

# Attribution, not wording. The same sentence leaks or does not depending on who is
# speaking, which is why this is asked of a model and not of a pattern.
COURT_THIS_CASE = "court_conclusion_this_case"
EARLIER_INSTANCE = "earlier_instance_same_case"
ADMISSIBILITY_ONLY = "court_admissibility_only"
PARTY_POSITION = "party_position"
OTHER_AUTHORITY = "other_case_or_domestic_court"
UNLABELLED = "unlabelled"

CATEGORIES = (COURT_THIS_CASE, EARLIER_INSTANCE, ADMISSIBILITY_ONLY,
              PARTY_POSITION, OTHER_AUTHORITY)

# Three tiers, because these are not the same finding and must not be pooled. A
# Chamber judgment quoted in a Grand Chamber case is the same application decided once
# already: not this Court's conclusion, yet it hands over the answer. A party's position
# is usually noise, but a Government concession is not, and no detector can tell those
# apart reliably -- that is what the human pass is for.
#
# Admissibility is its own class because the first run without it scored "this part of
# the application is manifestly ill-founded and must be rejected" as the Court's finding
# on the merits. It is the Court, it is this case, and it still does not say how the
# Article at issue came out, so pooling it inflated the leak tier.
TIERS = {COURT_THIS_CASE: "leak", EARLIER_INSTANCE: "leak",
         ADMISSIBILITY_ONLY: "review", PARTY_POSITION: "review",
         OTHER_AUTHORITY: "clean", UNLABELLED: "review"}

SPAN_TEMPLATE = """Below is the text of an ECtHR case as it is shown to a model that \
must predict whether Article {article} was violated. The operative part has been \
removed on purpose.

Case Name: {case_name}
Article at issue: {article}

---
{text}
---

Quote every sentence in the text above that reveals how the European Court of Human \
Rights resolved Article {article} in THIS case.

Rules:
1. Quote exactly. Copy the sentence character for character from the text above. Do \
not paraphrase, do not shorten, do not use an ellipsis, do not add quotation marks \
that are not in the text.
2. Label each quote with one of:
   - "court_conclusion_this_case": this Court stating its own finding on the merits of \
this application, including indirect wording such as "the respondent State did not fail \
to fulfil its positive obligations", and including a Registry keyword line of the form \
"Art 8 • Correspondence • ..." that summarises the outcome.
   - "earlier_instance_same_case": an earlier decision on this same application, such \
as a Chamber judgment in a case now before the Grand Chamber.
   - "court_admissibility_only": this Court ruling on admissibility alone, such as \
"this part of the application is manifestly ill-founded and must be rejected" or "the \
complaint must be declared admissible". Use this even though it is this Court and this \
case, because it does not say how Article {article} came out on the merits.
   - "party_position": what the applicant or the Government alleged, submitted, \
conceded or agreed.
   - "other_case_or_domestic_court": a finding in a different ECtHR case, including \
"cited above" and leading-case citations, or a decision of a domestic court.
3. Include a quote only if it concerns Article {article}. A conclusion about a \
different Article of the Convention is not relevant here.
4. If no sentence reveals the outcome, reply with an empty array. Abstaining is the \
correct answer when nothing qualifies; do not reach for the closest thing.

Reply with ONLY a JSON array, at most 5 items, each an object with keys "quote" and \
"category". Example:
[{{"quote": "Accordingly, the Court finds a violation of Article 5 § 4 of the \
Convention.", "category": "court_conclusion_this_case"}}]"""

# HUDOC text carries non-breaking spaces, soft hyphens and curly punctuation, and a
# model retyping a sentence normalises all of it. Comparing raw strings therefore
# rejects correct quotes; the fold below is what makes "verbatim" mean what a reader
# means by it, while keeping a map back to real offsets so the output stays checkable.
_TRANSLATE = {
    "‘": "'", "’": "'", "‚": "'", "′": "'",
    "“": '"', "”": '"', "„": '"', "″": '"',
    "–": "-", "—": "-", "−": "-", "­": "",
    " ": " ", " ": " ", " ": " ", " ": " ",
}


def prompt_digest(length=12):
    """Identity of the question that was asked.

    The checkpoint keys rows by it and the report filters on it, because the first run
    had no admissibility class: resuming that file under the amended prompt would have
    returned the old rows instantly and reported them as answers to the new question.
    Every rule the repository has written about stale artifacts is this failure.
    """
    return hashlib.sha256(SPAN_TEMPLATE.encode("utf-8")).hexdigest()[:length]


def _fold(text):
    """Whitespace- and punctuation-normalised text, plus a map to original offsets."""
    folded, offsets, previous_space = [], [], False
    for position, char in enumerate(text):
        char = _TRANSLATE.get(char, char)
        if char == "":
            continue
        if char.isspace():
            if previous_space:
                continue
            folded.append(" ")
            offsets.append(position)
            previous_space = True
        else:
            folded.append(char)
            offsets.append(position)
            previous_space = False
    return "".join(folded), offsets


def locate(quote, text):
    """Character span of `quote` inside `text`, or None when it is not there.

    A span that cannot be located is not a near miss to be salvaged: it is a sentence
    the model produced rather than found, and counting it would put invention into the
    leak rate. Callers drop it and record that they did.
    """
    if not quote or not text:
        return None
    needle, _ = _fold(quote)
    needle = needle.strip()
    if not needle:
        return None
    haystack, offsets = _fold(text)
    start = haystack.find(needle)
    if start < 0:
        start = haystack.lower().find(needle.lower())
    if start < 0:
        return None
    end = start + len(needle) - 1
    return offsets[start], offsets[end] + 1


def parse_spans(reply):
    """Pull [{quote, category}] out of a model reply, dropping what cannot be read.

    Fenced JSON is stripped before parsing rather than salvaged afterwards, for the
    reason given in `experiments/extractive.py`: a salvage that cuts back to the last
    complete element silently drops the final item of every batch.
    """
    if not reply or reply.startswith("ERROR:"):
        return []
    body = re.sub(r"^\s*```[a-z]*\s*|\s*```\s*$", "", reply.strip())
    if body.lstrip().startswith("{"):
        try:
            wrapper = json.loads(body)
        except json.JSONDecodeError:
            wrapper = {}
        if isinstance(wrapper, dict):
            for field in ("spans", "quotes", "results"):
                if isinstance(wrapper.get(field), list):
                    body = json.dumps(wrapper[field])
                    break
    low, high = body.find("["), body.rfind("]")
    if low < 0 or high <= low:
        return []
    try:
        items = json.loads(body[low:high + 1])
    except json.JSONDecodeError:
        return []
    spans = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        quote = (item.get("quote") or "").strip()
        if not quote:
            continue
        category = (item.get("category") or "").strip().lower()
        spans.append({"quote": quote,
                      "category": category if category in CATEGORIES else UNLABELLED})
    return spans


def verify(spans, text):
    """Keep the spans that are really in `text`, with their offsets; count the rest."""
    kept, dropped = [], []
    for span in spans:
        found = locate(span["quote"], text)
        if found is None:
            dropped.append(span["quote"])
            continue
        kept.append({**span, "start": found[0], "end": found[1],
                     "tier": TIERS[span["category"]]})
    return kept, dropped


def tier_of(spans):
    """The strongest tier among these spans: leak beats review beats clean."""
    tiers = {span["tier"] for span in spans}
    for tier in ("leak", "review", "clean"):
        if tier in tiers:
            return tier
    return "clean"
