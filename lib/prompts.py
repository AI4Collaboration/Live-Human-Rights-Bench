"""
Shared prompts and templates for ECHR case evaluation.
"""

# ECHR Article Titles
ARTICLE_TITLES = {
    "2": "Right to life",
    "3": "Prohibition of torture",
    "5": "Right to liberty and security",
    "6": "Right to a fair trial",
    "8": "Right to respect for private and family life",
    "10": "Freedom of expression",
    "14": "Prohibition of discrimination",
    "P1-1": "Protection of property",
}

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


# ============================================================================
# CONTAMINATION / ORDERS-OF-MEMORIZATION PROMPTS
# Ported from the contamination repo (MFT triple). Used by:
#   experiments/generate_mft.py, experiments/mft_evaluation.py
# ============================================================================

# Per-article doctrinal legal tests. Used by the MFT generator to instruct the
# model on which facts are *material* when compressing a case to its minimal
# functional version. Extend this dict as more articles appear in the data.
ARTICLE_LEGAL_TESTS = {
    "2": (
        "Article 2 (Right to life) concerns whether the State caused or failed to "
        "prevent loss of life, whether lethal force was absolutely necessary and "
        "proportionate, and whether the State conducted an effective official "
        "investigation into the death. Material facts: how the death or "
        "life-threatening situation arose, the State's involvement or knowledge, "
        "the use of force, and the adequacy of any investigation."
    ),
    "3": (
        "Article 3 (Prohibition of torture) concerns whether treatment or punishment "
        "reached the minimum level of severity to qualify as torture or inhuman or "
        "degrading treatment, and whether the State was responsible or failed to "
        "protect. Material facts: the nature, duration, and intensity of the "
        "treatment, its physical and mental effects, the vulnerability of the "
        "applicant, the context (e.g. detention, expulsion), and the State's role."
    ),
    "5": (
        "Article 5 (Right to liberty and security) concerns whether a deprivation of "
        "liberty fell within a permitted ground, followed a procedure prescribed by "
        "law, and was accompanied by required safeguards (prompt information, "
        "judicial review, trial within reasonable time, enforceable right to "
        "compensation). Material facts: the legal basis and ground for detention, "
        "its duration, procedural safeguards provided or denied, and access to "
        "judicial review."
    ),
    "6": (
        "Article 6 (Right to a fair trial) concerns whether, in the determination of "
        "civil rights and obligations or of a criminal charge, the applicant "
        "received a fair and public hearing within a reasonable time by an "
        "independent and impartial tribunal established by law, including access to "
        "a court, adversarial proceedings, equality of arms, and (in criminal "
        "cases) the presumption of innocence and minimum defence rights. Material "
        "facts: the nature of the proceedings, the specific fairness guarantee at "
        "issue (access, independence, length, adversarial process, reasoning of "
        "decisions), the conduct of the domestic courts, and the effect on the "
        "applicant."
    ),
    "8": (
        "Article 8 (Right to respect for private and family life) concerns whether "
        "there was an interference with private or family life, home, or "
        "correspondence, and if so whether the interference was in accordance with "
        "the law, pursued a legitimate aim, and was necessary in a democratic "
        "society (proportionate). Material facts: the nature of the interference, "
        "its legal basis, the aim pursued, and the proportionality considerations "
        "(severity, safeguards, balancing of interests)."
    ),
    "10": (
        "Article 10 (Freedom of expression) concerns whether there was an "
        "interference with expression, and if so whether it was prescribed by law, "
        "pursued a legitimate aim, and was necessary in a democratic society. "
        "Material facts: the expression at issue, the nature and severity of the "
        "restriction or sanction, the legal basis, the aim pursued, and the "
        "proportionality considerations."
    ),
    "14": (
        "Article 14 (Prohibition of discrimination) concerns whether there was a "
        "difference in treatment of persons in analogous situations, based on an "
        "identifiable ground, without objective and reasonable justification, within "
        "the ambit of another Convention right. Material facts: the difference in "
        "treatment, the ground of distinction, the comparator group, and any "
        "justification advanced by the State."
    ),
    "P1-1": (
        "Article 1 of Protocol No. 1 (Protection of property) concerns whether there "
        "was an interference with peaceful enjoyment of possessions, and if so "
        "whether it was lawful, pursued a legitimate aim in the general interest, "
        "and struck a fair balance between the general interest and the "
        "individual's rights (proportionality). Material facts: the possession at "
        "issue, the nature of the interference (deprivation, control of use, other), "
        "its legal basis, the aim pursued, and the balancing considerations."
    ),
}

# Fallback legal test for any article not enumerated above.
ARTICLE_LEGAL_TEST_FALLBACK = (
    "This Convention article concerns whether the State interfered with or failed "
    "to secure the protected right, and whether any interference was lawful, "
    "pursued a legitimate aim, and was proportionate. Material facts: the nature of "
    "the interference or failure, its legal basis, the aim pursued, and the "
    "proportionality or adequacy considerations."
)

# Minimum Functionality Test generator: compress a verdict-free case into a
# single paragraph containing ONLY the doctrinally material facts, with no
# outcome cues. The evaluator then judges this minimal version — a competence
# floor for the contamination hierarchy.
MFT_GENERATION_PROMPT = """You are preparing a minimal test version of an ECtHR case for a robustness study.

Your task: compress the case below into a SINGLE paragraph that contains ONLY the facts material to the legal test for Article {article} - {article_title}.

Legal test for this article:
{article_legal_test}

Rules:
1. Include ONLY facts that are doctrinally material to the Article {article} legal test described above. Omit procedural history, citations, peripheral parties, and background detail that does not bear on the legal test.
2. Do NOT include the Court's reasoning, findings, conclusions, or any statement of the outcome. Present only the pre-decisional factual situation.
3. Do NOT mention the case name or the names of the parties.
4. Write in neutral, factual language. Do not argue for or against a violation.
5. Output ONE paragraph only, approximately 80-150 words. No headings, no lists, no preamble.

Case text (verdict already removed):
{case_text}

Minimal one-paragraph version:"""
