"""Canonical evaluation-target semantics shared by runners and validators."""

from __future__ import annotations

import re


ARTICLE_TITLES = {
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
    "18": "Limitation on use of restrictions on rights",
    "34": "Individual applications",
    "38": "Examination of the case",
    "P1-1": "Protection of property",
    "P1-2": "Right to education",
    "P1-3": "Right to free elections",
    "P4-2": "Freedom of movement",
    "P4-4": "Prohibition of collective expulsion of aliens",
    "P7-2": "Right of appeal in criminal matters",
    "P7-4": "Right not to be tried or punished twice",
    "P12-1": "General prohibition of discrimination",
}

PROCEDURAL_PROVISIONS = {"34", "38"}


def provision_name(code: str) -> str:
    code = str(code).strip()
    match = re.fullmatch(r"P(\d+)-(\d+)", code)
    if match:
        protocol, article = match.groups()
        base = f"Article {article} of Protocol No. {protocol}"
    else:
        base = f"Article {code}"
    try:
        title = ARTICLE_TITLES[code]
    except KeyError as exc:
        raise ValueError(f"No title for target provision {code}") from exc
    return f"{base} ({title})"


def target_question(respondent: str, code: str, issue: str) -> str:
    respondent = str(respondent).strip()
    if not respondent:
        raise ValueError("Target respondent must be nonempty")
    issue = str(issue).strip()
    if not issue:
        raise ValueError("Target issue must be nonempty")
    return (
        f"whether the Court finds a violation by {respondent} of {provision_name(code)} "
        f"concerning {issue} in this case"
    )


def target_key(case: dict) -> tuple[str, str, str, str]:
    return (
        str(case["item_id"]),
        str(case["target_respondent_code"]),
        str(case["article_full"]),
        str(case["target_issue"]).casefold(),
    )


def target_stratum(code: str) -> str:
    return "procedural" if str(code) in PROCEDURAL_PROVISIONS else "substantive"
