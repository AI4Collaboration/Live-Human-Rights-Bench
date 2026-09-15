"""Offline Section 5 prompt assembly, not an experiment runner.

Checks cover structure and budgets, not semantic validity or elicitation efficacy.
No model clients, network calls, or changes to historical rq3 are involved.
"""

import json
import math
from numbers import Real
from pathlib import Path
from string import Formatter


PACK_PATH = Path(__file__).resolve().parents[1] / "configs" / "adversarial_opinion_prompts.json"
STRATEGIES = ("Baseline", "Authority", "Social proof", "Unity")
EVALUATION_DESIGN = {
    "modes": ["static", "adaptive"],
    "trajectories_per_mode": 1,
    "shared_saved_initial_response": True,
    "shared_turn_budget": True,
}


def load_prompt_pack(path=PACK_PATH):
    with Path(path).open(encoding="utf-8") as handle:
        pack = json.load(handle)
    if pack.get("cue_schedule") != "FIRST_TURN_ONLY":
        raise ValueError("Only the shared first-turn-only cue schedule is supported")
    if pack.get("evaluation_design") != EVALUATION_DESIGN:
        raise ValueError("Use one static and one adaptive trajectory with a shared initial response and turn budget")
    return pack


def _positive_integer(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be an explicit positive integer")
    return value


def initial_judgment(score):
    if isinstance(score, bool) or not isinstance(score, Real):
        raise ValueError("Initial score must be a finite number from 0 to 100")
    if not math.isfinite(score) or not 0 <= score <= 100:
        raise ValueError("Initial score must be a finite number from 0 to 100")
    if score < 40:
        return "no violation"
    if score > 60:
        return "a violation"
    raise ValueError("An initial abstention is not eligible for an opposing challenge")


def opposing_judgment(initial_score):
    return "a violation" if initial_judgment(initial_score) == "no violation" else "no violation"


def _case_fields(case):
    fields = {}
    for key in ("case_text", "target_provision"):
        value = case.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a nonempty string")
        fields[key] = value.strip()
    return fields  # Deliberately never copy gold labels or other case fields.


def _condition(pack, condition):
    allowed = {"strategy", "variation", "parameters", "pressure"}
    if set(condition) - allowed:
        raise ValueError("Unknown condition fields")
    strategy, variation = condition.get("strategy"), condition.get("variation")
    if strategy not in STRATEGIES or variation not in pack["cues"][strategy]:
        raise ValueError("Unknown strategy or cue variation")
    pressure = condition.get("pressure", pack["default_pressure"])
    if pressure not in pack["pressure"]:
        raise ValueError("Unknown pressure level")
    if strategy != "Baseline" and pressure != pack["cue_comparison_pressure"]:
        raise ValueError("Cue comparisons must use the fixed cue_comparison_pressure")
    params = dict(condition.get("parameters", {}))
    template = pack["cues"][strategy][variation]
    required = {field for _, field, _, _ in Formatter().parse(template) if field}
    if set(params) != required:
        raise ValueError(f"Cue parameters must be exactly {sorted(required)}")
    if "group_size" in params:
        _positive_integer(params["group_size"], "group_size")
        _positive_integer(params["agreement_count"], "agreement_count")
        if params["agreement_count"] > params["group_size"]:
            raise ValueError("agreement_count cannot exceed group_size")
    return strategy, pressure, template.format(**params)


def render_cue(pack, condition):
    return _condition(pack, condition)[2]


def build_initial_messages(pack, case):
    return [
        {"role": "system", "content": pack["target_system"]},
        {"role": "user", "content": pack["target_initial"].format(
            **_case_fields(case), response_request=pack["response_request"])},
    ]


def _deliver(pack, body, prefix, word_budget, cue=""):
    _positive_integer(word_budget, "word_budget")
    if not isinstance(body, str) or not body.strip():
        raise ValueError("Challenge body must be nonempty text")
    body = body.strip()
    if pack["response_request"] in body:
        raise ValueError("The software, not the challenge body, appends the output request")
    if cue and cue in body:
        raise ValueError("The cue introduction must not be repeated in the body")
    challenge = " ".join(part for part in (prefix, body) if part)
    if len(challenge.split()) > word_budget:
        raise ValueError("Challenge including its cue exceeds word_budget")
    return challenge + "\n\n" + pack["response_request"]


def build_static_sequence(pack, case, initial_score, condition, *, turns, word_budget):
    """Freeze all T user messages without reading post-challenge target replies."""
    _positive_integer(turns, "turns")
    _positive_integer(word_budget, "word_budget")
    _, pressure, cue = _condition(pack, condition)
    fields = _case_fields(case)
    values = dict(opposing_judgment=opposing_judgment(initial_score),
                  target_provision=fields["target_provision"])
    templates = pack["pressure"][pressure]
    return [_deliver(pack, templates["static_first" if turn == 1 else "static_later"].format(**values),
                     cue if turn == 1 else "", word_budget, cue)
            for turn in range(1, turns + 1)]


def _transcript(messages, turn):
    if not isinstance(messages, (list, tuple)) or len(messages) != 2 * turn:
        raise ValueError("Full transcript must contain the initial exchange and every preceding turn")
    clean = []
    for index, message in enumerate(messages):
        expected = "user" if index % 2 == 0 else "assistant"
        if message.get("role") != expected or not isinstance(message.get("content"), str):
            raise ValueError("Transcript must alternate user/assistant text and end with assistant")
        clean.append({"role": expected, "content": message["content"]})
    return clean  # Whitelist role/content and do not mutate caller-owned records.


def build_adaptive_messages(pack, case, initial_score, condition, conversation, *, turn, word_budget):
    """Return challenger inputs and assembly metadata, never a generated challenge."""
    _positive_integer(turn, "turn")
    _positive_integer(word_budget, "word_budget")
    strategy, pressure, cue = _condition(pack, condition)
    prefix = cue if turn == 1 else ""
    body_budget = word_budget - len(prefix.split())
    if body_budget < 1:
        raise ValueError("word_budget must leave room for a body after the cue")
    values = dict(_case_fields(case), initial_judgment=initial_judgment(initial_score),
                  opposing_judgment=opposing_judgment(initial_score), strategy=strategy,
                  cue_description=cue or "None",
                  pressure_name=pressure,
                  pressure_instruction=pack["pressure"][pressure]["adaptive_instruction"],
                  turn=turn, body_word_budget=body_budget,
                  conversation=json.dumps(_transcript(conversation, turn), ensure_ascii=False, indent=2))
    return {
        "messages": [{"role": "system", "content": pack["adaptive_system"].format(**values)},
                     {"role": "user", "content": pack["adaptive_user"].format(**values)}],
        "cue_prefix": prefix, "fixed_cue": cue,
        "body_word_budget": body_budget, "word_budget": word_budget,
    }


def assemble_adaptive_challenge(pack, adaptive_input, body):
    return _deliver(pack, body, adaptive_input["cue_prefix"],
                    adaptive_input["word_budget"], adaptive_input["fixed_cue"])


def build_consistency_followup(pack, initial_score, reversed_score):
    """Render only for a decided reversal; caller must place it on a separate branch."""
    if initial_judgment(reversed_score) != opposing_judgment(initial_score):
        raise ValueError("Consistency follow-up requires a decided reversal")
    return pack["consistency"].format(initial_judgment=initial_judgment(initial_score)) + "\n\n" + pack["response_request"]
