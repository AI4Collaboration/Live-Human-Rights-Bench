#!/usr/bin/env python3
"""Print exact offline prompts on an explicitly labeled toy case."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from experiments.adversarial_prompts import (STRATEGIES, build_adaptive_messages,
    build_initial_messages, build_static_sequence, load_prompt_pack)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--turns", type=int, required=True)
    parser.add_argument("--word-budget", type=int, required=True)
    parser.add_argument("--strategy", choices=STRATEGIES)
    parser.add_argument("--pressure", choices=("low", "high"), default="high")
    args = parser.parse_args()
    if args.pressure == "low" and args.strategy != "Baseline":
        parser.error("Low pressure is the Baseline contrast; use --strategy Baseline")
    pack = load_prompt_pack()
    case = {"case_text": "[TOY CASE, NOT EXPERIMENTAL DATA] A person describes overcrowded detention and limited time outside the cell.",
            "target_question": "whether the Court finds a violation by State A of Article 3 concerning overcrowded detention conditions in this case",
            "target_respondent": "State A", "target_provision": "Article 3",
            "target_issue": "overcrowded detention conditions"}
    conditions = {
        "Baseline": {"strategy": "Baseline", "variation": "none"},
        "Authority": {"strategy": "Authority", "variation": "senior_lawyer"},
        "Social proof": {"strategy": "Social proof", "variation": "reviewers",
                         "parameters": {"group_size": 5, "agreement_count": 5}},
        "Unity": {"strategy": "Unity", "variation": "shared"},
    }
    initial = build_initial_messages(pack, case)
    transcript = [initial[1], {"role": "assistant", "content": json.dumps({
        "violation_likelihood": 80,
        "explanation": "The described conditions suggest a violation."})}]
    print("OFFLINE TOY PREVIEW: score 80 and cue levels are illustrative, not selected experiment settings.")
    print("No model is called. Adaptive text below is challenger input, not a generated challenge.")
    print("Protocol: one static trajectory and one adaptive trajectory per condition, sharing the saved initial response and T.")
    print(pack["validation_note"])
    for message in initial:
        print(f"\nINITIAL {message['role'].upper()}\n{message['content']}")
    for strategy in ([args.strategy] if args.strategy else STRATEGIES):
        condition = dict(conditions[strategy], pressure=args.pressure)
        try:
            sequence = build_static_sequence(pack, case, 80, condition,
                turns=args.turns, word_budget=args.word_budget)
            adaptive = build_adaptive_messages(pack, case, 80, condition, transcript,
                turn=1, word_budget=args.word_budget)
        except ValueError as error:
            parser.error(str(error))
        print(f"\n=== {strategy}: {json.dumps(condition)} ===")
        for turn, text in enumerate(sequence, 1):
            print(f"\nSTATIC TARGET USER MESSAGE {turn}/{args.turns}\n{text}")
        print("\nADAPTIVE TURN 1 INPUT (later inputs require actual preceding replies)")
        for message in adaptive["messages"]:
            print(f"\nCHALLENGER {message['role'].upper()}\n{message['content']}")
        print(f"\nSoftware fixed prefix: {adaptive['fixed_prefix']!r}")
        print(f"Generated-body allowance: {adaptive['body_word_budget']} words")
        print(f"Identical software suffix:\n{pack['response_request']}")


if __name__ == "__main__":
    main()
