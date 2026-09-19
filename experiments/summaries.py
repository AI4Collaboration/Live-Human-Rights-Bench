"""Case summaries as a shared artifact, produced once by a fixed summariser.

Generate one summary per judgment with a fixed summarizer, then reuse it across
target models and articles. This keeps generation independent of the evaluator.
The JSON array has exactly one slot; historical multi-draw files are rejected.
"""

import json
import re
import os
import sys

SUMMARY_TEMPLATE = """Summarize the following legal case to approximately 500 words, focusing on the key facts relevant to the alleged violation(s).

Case Name: {case_name}
Full Text:
{full_text}

Summary (approximately 500 words):"""

LEAK_SAFE_SUMMARY_TEMPLATE_V2 = """Summarize the factual record below in approximately 500 words. Focus only on facts relevant to the alleged violation(s), including the parties, domestic proceedings, concrete events, dates, and the parties' allegations or arguments when useful.

Do not state or imply the current ECtHR judgment's outcome. Do not narrate the current ECtHR's merits reasoning, assessment, treatment of unilateral declarations, application of precedent, or award. Do not predict what the current ECtHR likely decided. Omit current-judgment preambles about well-established case-law. Earlier judgments and domestic decisions may be described only when clearly identified as earlier or domestic proceedings. If the supplied text contains little beyond procedure and factual tables, summarize those facts without filling gaps from memory.

Case Name: {case_name}
Full Text:
{full_text}

Factual summary (approximately 500 words):"""


LEAK_SAFE_SUMMARY_TEMPLATE = """Summarize the factual record below in approximately 500 words. Focus only on facts relevant to the alleged violation(s), including the parties, domestic proceedings, concrete events, dates, and the parties' allegations or arguments when useful.

Do not state or imply the current ECtHR judgment's outcome. Do not narrate the current ECtHR's merits reasoning, assessment, application of precedent, or award. Omit unilateral declarations, friendly-settlement negotiations, strike-out or restoration decisions, admissibility rulings, and current-judgment preambles about well-established case-law. Do not predict the current ECtHR's decision, the applicable Convention provision, or the legal issue when the supplied record does not state it. Earlier judgments and domestic decisions may be described only when clearly identified as earlier or domestic proceedings. If the supplied text contains little beyond procedure and factual tables, summarize those facts without filling gaps from memory.

Case Name: {case_name}
Full Text:
{full_text}

Factual summary (approximately 500 words):"""


def is_usable(summary):
    """True when this is a summary rather than a record of a failed call.

    A failed call returns the string "ERROR: ...", which is not empty and would
    otherwise be scored as if it were a summary -- the same defect as the old
    fall-back to raw case text, which silently mixed the two conditions.
    """
    return isinstance(summary, str) and bool(summary.strip()) and not summary.strip().startswith("ERROR:")


def appears_truncated(summary):
    """Reject prose that ends mid-sentence even when an API marked it complete."""
    if not is_usable(summary):
        return True
    return re.search(r'[.!?…][\"”’\]\)]*$', summary.rstrip()) is None


def load_summaries(path):
    """Return (summaries, meta) from a summaries file.

    Accept the wrapped artifact or a bare ``{item_id: [summary]}`` mapping.
    Each judgment has exactly one slot. Historical multi-draw files are rejected,
    never silently truncated or pooled.
    """
    with open(path) as f:
        blob = json.load(f)
    if isinstance(blob, dict) and "summaries" in blob:
        mapping, meta = blob["summaries"], {k: v for k, v in blob.items() if k != "summaries"}
    else:
        mapping, meta = blob, {}
    if meta.get("versions", 1) != 1:
        raise ValueError("Only one summary per judgment is supported; use the current single-summary release")
    validate_single_summaries(mapping)
    return mapping, meta


def validate_single_summaries(mapping):
    if not isinstance(mapping, dict):
        raise ValueError("Summaries must be a judgment-to-single-summary mapping")
    for item_id in mapping:
        summary_for(mapping, item_id)


def summary_for(mapping, item_id):
    """Read the only summary, rejecting any multi-draw input."""
    if item_id not in mapping:
        return None
    values = mapping[item_id]
    if not isinstance(values, list) or len(values) != 1:
        raise ValueError(f"Exactly one summary is required for {item_id}")
    return values[0]


# A summarizer can recognize the case and supply its outcome from memory. This
# lexical screen catches candidates; the canonical release also needs grounded
# review of the current Court's reasoning and conclusion.
_STATES_OUTCOME = re.compile(
    r"(the Court (found|held|concluded|ruled)[^.]{0,60}(violation|no violation)"
    r"|there (has|had) been (a|no) violation"
    r"|(was|were) found to (have )?violat"
    r"|\b(constituted|constitutes|amounted|amounts)(?: to)? (a|no) violation)", re.I)

_CURRENT_COURT_ASSESSMENT = re.compile(
    r"\b(?:[Tt]he (?:European )?Court|[Tt]he ECtHR|ECtHR)(?:'s|’s)?\s+"
    r"(?:judgment\s+)?(?:likely|probably|potentially|noted|considered|examined|"
    r"rejected|accepted|determined|indicated|recognised|recognized|addressed|awarded)\b",
)

_INDIRECT_OUTCOME_SIGNAL = re.compile(
    r"\bunilateral declarations?\b"
    r"|\b(?:the )?(?:Government|respondent State)\b[^.]{0,180}"
    r"\b(?:admitted|acknowledged|conceded)\b[^.]{0,180}\b(?:violation|breach)\b"
    r"|\bthe (?:European )?Court\b[^.]{0,140}"
    r"\b(?:struck|strike|restored)\b[^.]{0,100}\b(?:application|complaint|list)\b"
    r"|\b(?:case|complaint|alleged violation|legal issue)\b[^.]{0,100}"
    r"\b(?:likely|probably|potentially)\b[^.]{0,100}\b(?:Article|Convention|Court|case-law)\b",
    re.I,
)

def asserts_outcome(summary, source_text):
    """Flag outcome-wording candidates for rejection or contextual review.

    An unrelated domestic finding in the source must not exempt a summary that
    states the current ECtHR verdict. This screen is deliberately conservative;
    approved benchmark inputs additionally require evidence-grounded review.
    The source argument remains for compatibility with existing generators.
    """
    if not summary or not isinstance(summary, str):
        return False
    return bool(_STATES_OUTCOME.search(summary))


def narrates_current_court_assessment(summary):
    """Conservative candidate screen for current-case reasoning or prediction."""
    if not summary or not isinstance(summary, str):
        return False
    return bool(
        _CURRENT_COURT_ASSESSMENT.search(summary)
        or _INDIRECT_OUTCOME_SIGNAL.search(summary)
    )


def add_argument(parser):
    """The --summaries flag, identical in every runner."""
    parser.add_argument("--summaries", help="approved single-summary JSON artifact; "
                                            "required for the rq1 summary comparison")


def load_summaries_for(args, stages, mlflow=None):
    """Load the shared summaries if these stages need them, or exit saying why.

    The summary comparison uses one reviewed summary shared across target models.
    """
    if "rq1" not in stages:
        return {}
    path = getattr(args, "summaries", None)
    if not path:
        sys.exit("ERROR: --summaries is required for rq1. Supply the reviewed "
                 "single-summary artifact shared by all target models.")
    if not os.path.exists(path):
        sys.exit(f"ERROR: no such summaries file: {path}")
    summaries, meta = load_summaries(path)
    from input_gate import verify_summaries
    verify_summaries(summaries, metadata=meta)
    if mlflow is not None:
        mlflow.log_param("summarizer", meta.get("summarizer", "unknown"))
        mlflow.log_param("summaries_file", os.path.basename(path))
        mlflow.log_param("summary_dataset_id", meta.get("dataset_id", "unrecorded"))
    print(f"Summaries: {len(summaries)} judgments from "
          f"{meta.get('summarizer', 'an unrecorded summariser')}\n")
    return summaries


def coverage(summaries, cases):
    """How many instances have their one usable summary."""
    have = sum(is_usable(summary_for(summaries, c["item_id"])) for c in cases)
    return have, len(cases)
