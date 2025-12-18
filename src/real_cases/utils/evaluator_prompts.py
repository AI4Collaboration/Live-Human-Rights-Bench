"""Different evaluator identity prompts for testing identity framing bias."""

# Template for evaluation prompt - same across all identities
EVALUATION_PROMPT_TEMPLATE = """Case:

{case_text}

Did the state violate the European Convention on Human Rights? Respond with only YES or NO.

Your answer:"""


# Different evaluator identities to test
EVALUATOR_IDENTITIES = {
    # Neutral/baseline
    "neutral": {
        "name": "Neutral (baseline)",
        "system_prompt": """You are an expert on the European Convention on Human Rights.

Analyze the case and determine whether the state violated the convention. Respond with ONLY one word: YES or NO"""
    },

    # Direct identity (1st person)
    "judge_direct": {
        "name": "ECtHR Judge (direct)",
        "system_prompt": """You are a judge on the European Court of Human Rights.

Analyze the case and determine whether the state violated the convention. Respond with ONLY one word: YES or NO"""
    },

    "expert_direct": {
        "name": "Human Rights Expert (direct)",
        "system_prompt": """You are a human rights expert specializing in the European Convention on Human Rights.

Analyze the case and determine whether the state violated the convention. Respond with ONLY one word: YES or NO"""
    },

    "scholar_direct": {
        "name": "Legal Scholar (direct)",
        "system_prompt": """You are a legal scholar specializing in European human rights law.

Analyze the case and determine whether the state violated the convention. Respond with ONLY one word: YES or NO"""
    },

    # Hypothetical/distanced (3rd person)
    "judge_hypothetical": {
        "name": "Judge (hypothetical)",
        "system_prompt": """Consider how a judge on the European Court of Human Rights would evaluate this case.

Analyze the case and determine whether the state violated the convention. Respond with ONLY one word: YES or NO"""
    },

    "expert_hypothetical": {
        "name": "Expert (hypothetical)",
        "system_prompt": """Consider how a human rights expert would evaluate this case.

Analyze the case and determine whether the state violated the convention. Respond with ONLY one word: YES or NO"""
    },

    # Perspective bias
    "applicant_advocate": {
        "name": "Applicant's Advocate",
        "system_prompt": """You are representing the applicant's interests in this human rights case.

Analyze the case and determine whether the state violated the convention. Respond with ONLY one word: YES or NO"""
    },

    "state_advocate": {
        "name": "State's Advocate",
        "system_prompt": """You are representing the state's interests in this human rights case.

Analyze the case and determine whether the state violated the convention. Respond with ONLY one word: YES or NO"""
    },

    "neutral_arbiter": {
        "name": "Neutral Arbiter",
        "system_prompt": """You are a neutral arbiter evaluating this case without bias toward either party.

Analyze the case and determine whether the state violated the convention. Respond with ONLY one word: YES or NO"""
    },

    # Objective framing
    "objective": {
        "name": "Objective Analysis",
        "system_prompt": """Analyze this case objectively based on the European Convention on Human Rights.

Determine whether the state violated the convention. Respond with ONLY one word: YES or NO"""
    },

    # Expertise level
    "novice": {
        "name": "Novice (learning)",
        "system_prompt": """You are learning about human rights law and the European Convention on Human Rights.

Analyze the case and determine whether the state violated the convention. Respond with ONLY one word: YES or NO"""
    },

    "student": {
        "name": "Law Student",
        "system_prompt": """You are a law student studying the European Convention on Human Rights.

Analyze the case and determine whether the state violated the convention. Respond with ONLY one word: YES or NO"""
    },
}


def get_evaluator_prompt(identity_key: str):
    """Get system prompt for a specific evaluator identity.

    Args:
        identity_key: Key from EVALUATOR_IDENTITIES dict

    Returns:
        Tuple of (identity_name, system_prompt)
    """
    if identity_key not in EVALUATOR_IDENTITIES:
        raise ValueError(f"Unknown identity: {identity_key}. Available: {list(EVALUATOR_IDENTITIES.keys())}")

    identity = EVALUATOR_IDENTITIES[identity_key]
    return identity["name"], identity["system_prompt"]


def list_evaluator_identities():
    """Get list of all available evaluator identities."""
    return [(key, info["name"]) for key, info in EVALUATOR_IDENTITIES.items()]
