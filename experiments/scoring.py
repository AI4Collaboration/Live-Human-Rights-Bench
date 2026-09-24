"""Response parsing and category aggregation for 0-100 violation likelihoods.

Scores above 60 indicate violation, scores below 40 indicate no violation, and
40-60 indicate abstention. Missing or malformed responses remain unparsed.
Stored category-plurality decisions are distinct from the manuscript's mean-score
analysis; plurality ties are abstentions.
"""

import re
from collections import Counter

# Source character cap used by the full-case and paraphrase runners.
MAX_CASE_CHARS = 50_000

# A 0-100 likelihood, anchored at the end of the response so that numbers quoted
# in a preamble (article numbers, paragraph references, HTTP status codes) cannot
# be mistaken for the answer.
#
RATING = re.compile(r"(?<![0-9.])(\d{1,3})\s*%?\s*[.]?\s*$")

# A trailing number is only the answer if it is not the tail of a citation: a model
# replying "Article 8" would otherwise be scored 8, i.e. a confident no-violation.
CITATION_TAIL = re.compile(r"(?:article|paragraph|protocol|no\.|§)\s*\d{1,3}\s*%?\s*[.]?\s*$", re.I)

VIOLATION_ABOVE = 60    # a violation prediction
NO_VIOLATION_BELOW = 40  # a no-violation prediction; between the two is abstention

# Counts responses that carried no rating. Read it after a run: a non-zero value
# means calls failed, and those rows are not abstentions.
unparsed = Counter()


def parse_rating(response, tag="unknown"):
    """Return the 0-100 likelihood, or None when the response does not carry one."""
    if not response:
        unparsed[tag] += 1
        return None
    text = str(response).strip()
    match = RATING.search(text)
    if match is None or CITATION_TAIL.search(text) or not 0 <= int(match.group(1)) <= 100:
        unparsed[tag] += 1
        return None
    return int(match.group(1))


def _thresholded(ratings):
    """Each parsed sample as a category."""
    out = []
    for rating in ratings:
        if rating is None:
            continue
        if rating > VIOLATION_ABOVE:
            out.append("violation")
        elif rating < NO_VIOLATION_BELOW:
            out.append("no_violation")
        else:
            out.append("abstention")
    return out


def majority_vote(ratings):
    """Aggregate samples into (prediction, abstained), ignoring unparsed ones.

    Returns (None, False) when nothing could be parsed: a failed call is not a
    prediction and must not be recorded as an abstention.

    A tie is an abstention, which is what both the protocol and the paper say:
    "if no category receives a strict majority, including cases dominated by
    abstentions or evenly split votes, the aggregated prediction will be assigned
    as abstention". `Counter.most_common(1)` does not implement that. On a tie it
    returns whichever category was inserted first, so `[90, 20, 50]` scored
    "violation" and the same three samples in the order `[20, 90, 50]` scored
    "no_violation": the verdict depended on the order the samples came back in.
    1,641 of 96,959 stored rows were decided this way, and 1,193 of them were
    recorded as taking a side.

    The existing tests could not catch it because every one of them voted
    unanimously.
    """
    parsed = [r for r in ratings if r is not None]
    if not parsed:
        return None, False
    counts = Counter(_thresholded(parsed))
    ranked = counts.most_common()
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return "abstention", True
    return ranked[0][0], ranked[0][0] == "abstention"


def abstention_kind(ratings):
    """Why a row abstained: the model sat in the middle, or its samples split.

    Distinguish midpoint scores from ties between disagreeing samples.
    Both are derived from stored ratings without new model requests.
    """
    prediction, abstained = majority_vote(ratings)
    if not abstained:
        return None
    counts = Counter(_thresholded([r for r in ratings if r is not None]))
    ranked = counts.most_common()
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return "split"
    return "band"


def count_unparsed(ratings):
    """How many samples in this row carried no rating.

    The raw `ratings` list keeps None for a failed call, which is the honest record
    but trips any analysis that reaches for min/max/sum without filtering. Storing
    the count alongside means a reader does not have to infer it.
    """
    return sum(1 for r in ratings if r is None)


def mean_rating(ratings):
    """Mean of the parsed samples, or None when none parsed.

    `parse_rating` can now return None, so the plain `sum(r) / len(r)` the
    runners used would raise on the first failed call.
    """
    parsed = [r for r in ratings if r is not None]
    return sum(parsed) / len(parsed) if parsed else None
