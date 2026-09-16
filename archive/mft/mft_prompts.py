"""Archived prompts for the discontinued Minimum Functionality Test arm."""

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

ARTICLE_LEGAL_TEST_FALLBACK = (
    "This Convention article concerns whether the State interfered with or failed "
    "to secure the protected right, and whether any interference was lawful, "
    "pursued a legitimate aim, and was proportionate. Material facts: the nature of "
    "the interference or failure, its legal basis, the aim pursued, and the "
    "proportionality or adequacy considerations."
)

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
