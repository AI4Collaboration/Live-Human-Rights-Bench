"""Convention and Protocol provision names keyed by article_full."""
import logging

logger = logging.getLogger(__name__)

# ECHR article titles, keyed on the protocol-aware code used in `article_full`.
# The Convention's own headings; protocol provisions are keyed "P<protocol>-<art>".
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
