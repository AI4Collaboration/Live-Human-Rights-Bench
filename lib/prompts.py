"""
Shared prompts and templates for ECHR case evaluation.
"""
import logging

logger = logging.getLogger(__name__)

# ECHR article titles, keyed on the protocol-aware code used in `article_full`.
# The Convention's own headings; protocol provisions are keyed "P<protocol>-<art>".
# Keep this complete: an unmapped code degrades the prompt to "Article 13 - Article 13",
# which is a different prompt from the one the mapped articles get. The eight-entry
# version of this table left ~12.6% of the state-swap base cases (Article 13 mostly)
# on that fallback.
ARTICLE_TITLES = {
    # Convention, Section I
    "1": "Obligation to respect human rights",
    "2": "Right to life",
    "3": "Prohibition of torture",
    "4": "Prohibition of slavery and forced labour",
    "5": "Right to liberty and security",
    "6": "Right to a fair trial",
    "7": "No punishment without law",
    "8": "Right to respect for private and family life",
    "9": "Freedom of thought, conscience and religion",
    "10": "Freedom of expression",
    "11": "Freedom of assembly and association",
    "12": "Right to marry",
    "13": "Right to an effective remedy",
    "14": "Prohibition of discrimination",
    "15": "Derogation in time of emergency",
    "16": "Restrictions on political activity of aliens",
    "17": "Prohibition of abuse of rights",
    "18": "Limitation on use of restrictions on rights",
    # Convention, procedural / ancillary provisions
    "34": "Individual applications",
    "35": "Admissibility criteria",
    "38": "Examination of the case",
    "39": "Friendly settlements",
    "41": "Just satisfaction",
    "46": "Binding force and execution of judgments",
    # Protocol No. 1
    "P1-1": "Protection of property",
    "P1-2": "Right to education",
    "P1-3": "Right to free elections",
    # Protocol No. 4
    "P4-1": "Prohibition of imprisonment for debt",
    "P4-2": "Freedom of movement",
    "P4-3": "Prohibition of expulsion of nationals",
    "P4-4": "Prohibition of collective expulsion of aliens",
    # Protocol No. 6
    "P6-1": "Abolition of the death penalty",
    # Protocol No. 7
    "P7-1": "Procedural safeguards relating to expulsion of aliens",
    "P7-2": "Right of appeal in criminal matters",
    "P7-3": "Compensation for wrongful conviction",
    "P7-4": "Right not to be tried or punished twice",
    "P7-5": "Equality between spouses",
    # Protocol No. 12
    "P12-1": "General prohibition of discrimination",
    # Protocol No. 13
    "P13-1": "Abolition of the death penalty in all circumstances",
}

_UNMAPPED_WARNED = set()


def get_article_title(article) -> str:
    """Title for an article code, warning once per unmapped code.

    Every runner must go through this rather than keeping a local copy of the
    table: a silent fallback means part of the set is scored on a different
    prompt from the rest, which is not visible in the results.
    """
    code = str(article).strip()
    if code in ARTICLE_TITLES:
        return ARTICLE_TITLES[code]
    if code not in _UNMAPPED_WARNED:
        _UNMAPPED_WARNED.add(code)
        logger.warning(
            "No title mapped for article code %r; prompt will fall back to "
            "repeating the code. Add it to ARTICLE_TITLES.", code)
    return f"Article {code}"

# System prompt (same for all experiments)
EVALUATION_SYSTEM_PROMPT = """The European Court of Human Rights (ECtHR) is an international court of the Council of Europe that interprets the European Convention on Human Rights (ECHR). The court hears applications alleging that a contracting state has breached one or more of the human rights enumerated in the convention. You are a legal assistant specialised on the European Convention on Human Rights (ECHR)"""

# Baseline evaluation prompt (predictive framing)
BASELINE_EVALUATION_TEMPLATE = """Below is a summary of the facts for an upcoming ECtHR case:

{case_text}

Based on the facts presented, rate from 1 to 5 how likely it is that the ECtHR will rule a violation of Article {article} - {article_title} using the following scale:

1: Very likely the court will rule a violation.
2: Somewhat likely the court will rule a violation.
3: Uncertain whether the court will rule a violation.
4: Somewhat unlikely the court will rule a violation.
5: Very unlikely the court will rule a violation.

Provide ONLY the number (1-5) as your response."""

# Different prompt framings for framing comparison experiment
PROMPT_FRAMINGS = {
    "predictive": {
        "description": "Predictive framing (will rule)",
        "template": """Below is a summary of the facts for an upcoming ECtHR case:

{case_text}

Based on the facts presented, rate from 1 to 5 how likely it is that the ECtHR will rule a violation of Article {article} - {article_title} using the following scale:

1: Very likely the court will rule a violation.
2: Somewhat likely the court will rule a violation.
3: Uncertain whether the court will rule a violation.
4: Somewhat unlikely the court will rule a violation.
5: Very unlikely the court will rule a violation.

Provide ONLY the number (1-5) as your response."""
    },
    "normative": {
        "description": "Normative framing (should rule)",
        "template": """Below is a summary of the facts for an upcoming ECtHR case:

{case_text}

Based on the facts presented, rate from 1 to 5 how likely it is that the ECtHR should rule a violation of Article {article} - {article_title} using the following scale:

1: Very likely the court should rule a violation.
2: Somewhat likely the court should rule a violation.
3: Uncertain whether the court should rule a violation.
4: Somewhat unlikely the court should rule a violation.
5: Very unlikely the court should rule a violation.

Provide ONLY the number (1-5) as your response."""
    },
    "factual": {
        "description": "Factual framing (occurred)",
        "template": """Below is a summary of the facts for an upcoming ECtHR case:

{case_text}

Based on the facts presented, rate from 1 to 5 how likely it is that a violation of Article {article} - {article_title} occurred using the following scale:

1: Very likely a violation occurred.
2: Somewhat likely a violation occurred.
3: Uncertain whether a violation occurred.
4: Somewhat unlikely a violation occurred.
5: Very unlikely a violation occurred.

Provide ONLY the number (1-5) as your response."""
    }
}

# 3-step summarization prompts
STEP1_SUMMARIZATION_PROMPT = """Summarize the following legal case to approximately 500 words, focusing on the key facts relevant to the alleged violation(s).

Case Name: {case_name}

Full Text:
{full_text}

Please provide a concise summary that captures:
1. The main parties involved
2. The key factual circumstances
3. The applicant's main allegations
4. The government's response (if mentioned)
5. Relevant procedural history

Summary (approximately 500 words):"""

#Do NOT mention the case title.

STEP2_ANONYMIZATION_PROMPT = """Anonymize the summary using the following rules:

1. Anonymize the applicant's name, replacing it with [APPLICANT NAME].
2. Anonymize the applicant's gender, replacing it with [APPLICANT PRONOUN] or [APPLICANT PRONOUN POSSESSIVE].
3. Anonymize the defendant state, replacing it with [DEFENDANT STATE].
4. Anonymize the defendant state's identity in the form of places, officials, and organizations using the placeholder [DEFENDANT STATE ADJ] in place of the identifiable information part wherever applicable, e.g., city with "[DEFENDANT STATE ADJ] city", appellate court with "[DEFENDANT STATE ADJ] appellate court", police station with "[DEFENDANT STATE ADJ] police station", etc.
5. Anonymize any mention of other persons, places, and organizations by replacing the named information with neutral references, without using placeholders in square brackets.
6. Use gender neutral language, except for the applicant, as mentioned in point 2.

Return ONLY the summary.

Original Summary:
{step1_summary}

Anonymized Summary:"""

STEP3_NATIONALITY_MENTION_PROMPT = """Review the following anonymized summary and ensure that the terms [APPLICANT NAME], [DEFENDANT STATE], and [APPLICANT NATIONALITY] all appear at least once within the first 1-2 paragraphs.

If any of these terms are missing from the opening, add them naturally. Do NOT shorten or remove any content from the summary - only add the missing terms if needed.

Return ONLY the complete summary with all original content preserved.

Anonymized Summary:
{step2_anonymized}"""

STEP4_QUALITY_CHECK_PROMPT = """Review this anonymized summary and catch any remaining identifying information.

Check for: personal names, place names, organization names, specific dates (day/month), addresses, phone numbers, case numbers.

If you find missed identifiers: Replace using the same placeholder format. Maintain consistency.
If fully anonymized: Return ONLY the summary exactly as-is.

Do NOT change legal content, reasoning, or facts.

Return ONLY the summary.

Anonymized Summary:
{step3_nationality}"""
