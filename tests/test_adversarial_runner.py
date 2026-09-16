"""Offline checks for the summary-only three-turn sycophancy runner."""

import json
from pathlib import Path
from types import SimpleNamespace

from experiments.adversarial_prompts import (
    build_adaptive_messages,
    build_static_sequence,
    load_prompt_pack,
)
from experiments.run_adversarial_opinion import (
    adaptive_trajectory,
    metrics,
    parse_assessment,
    prompt_case,
    static_trajectory,
)
from experiments.targets import provision_name, target_question


ROOT = Path(__file__).resolve().parents[1]


class QueueClient:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self.create)
        )

    def create(self, **kwargs):
        self.calls.append(kwargs)
        content = self.outputs.pop(0)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )


def fixture_case():
    respondent = "State A"
    article = "3"
    issue = "detention conditions"
    return {
        "item_id": "fixture",
        "case_name": "Fixture v. State A",
        "article": article,
        "article_full": article,
        "violation_label": "violation",
        "full_case_text_no_verdict": "RAW_FULL_TEXT_MUST_NOT_APPEAR",
        "target_respondent_code": "AAA",
        "target_respondent": respondent,
        "target_provision": provision_name(article),
        "target_issue": issue,
        "target_aspect": "substantive",
        "target_question": target_question(respondent, article, issue),
        "target_status": "verified",
    }


def assessment(score):
    return json.dumps({
        "violation_likelihood": score,
        "explanation": "One concise reason.",
    })


def adaptive_output(view, reason):
    return json.dumps({
        "target_respondent": view["target_respondent"],
        "target_provision": view["target_provision"],
        "target_issue": view["target_issue"],
        "reason": reason,
    })


def test_prompt_case_is_summary_only_and_omits_gold():
    case = fixture_case()
    view = prompt_case(case, "REVIEWED_SUMMARY_ONLY")
    assert view["case_text"] == "REVIEWED_SUMMARY_ONLY"
    assert "violation_label" not in view
    assert "full_case_text_no_verdict" not in view
    assert "RAW_FULL_TEXT_MUST_NOT_APPEAR" not in json.dumps(view)


def test_static_and_adaptive_share_initial_and_run_exactly_three_turns():
    pack = load_prompt_pack()
    case = fixture_case()
    summary = "REVIEWED_SUMMARY_ONLY"
    view = prompt_case(case, summary)
    initial = {
        "score": 80.0,
        "response_raw": assessment(80),
        "explanation": "Initial view.",
    }
    condition = {
        "strategy": "Authority",
        "variation": "senior_lawyer",
        "pressure": "high",
        "parameters": {},
    }

    static_client = QueueClient([assessment(70), assessment(30), assessment(20)])
    static = static_trajectory(
        static_client, "target", case, summary, initial, condition, pack,
        turns=3, word_budget=55, temperature=0,
    )
    assert [row["turn"] for row in static] == [1, 2, 3]

    challenger_client = QueueClient([
        adaptive_output(view, "The explanation overlooks the available domestic step."),
        adaptive_output(view, "The latest answer does not address the key factual sequence."),
        adaptive_output(view, "The stated inference is not supported by the summarized record."),
    ])
    adaptive_target = QueueClient([assessment(70), assessment(30), assessment(20)])
    adaptive = adaptive_trajectory(
        adaptive_target, "target", challenger_client, "challenger",
        case, summary, initial, condition, pack, turns=3, word_budget=55,
        target_temperature=0, challenger_temperature=0,
    )
    assert [row["turn"] for row in adaptive] == [1, 2, 3]
    for call in static_client.calls + adaptive_target.calls + challenger_client.calls:
        serialized = json.dumps(call["messages"])
        assert "RAW_FULL_TEXT_MUST_NOT_APPEAR" not in serialized
    for call in static_client.calls + adaptive_target.calls:
        assert any(
            message.get("role") == "assistant"
            and message.get("content") == initial["response_raw"]
            for message in call["messages"]
        )


def test_registered_conditions_fit_every_real_target():
    pack = load_prompt_pack()
    rows = json.loads((ROOT / "data/processed/echr_unified.json").read_text(encoding="utf-8"))
    summaries = json.loads(
        (ROOT / "data/processed/summaries_dsv41flash.json").read_text(encoding="utf-8")
    )["summaries"]
    design = json.loads(
        (ROOT / "configs/adversarial_opinion_conditions.json").read_text(encoding="utf-8")
    )
    assert design["turns"] == 3
    assert len(design["conditions"]) == 9
    for case in rows:
        view = prompt_case(case, summaries[case["item_id"]][0])
        transcript = [
            {"role": "user", "content": "initial"},
            {"role": "assistant", "content": assessment(80)},
        ]
        for condition in design["conditions"]:
            spec = {name: condition[name] for name in (
                "strategy", "variation", "pressure", "parameters"
            )}
            assert len(build_static_sequence(
                pack, view, 80, spec, turns=3, word_budget=design["word_budget"]
            )) == 3
            adaptive = build_adaptive_messages(
                pack, view, 80, spec, transcript, turn=1,
                word_budget=design["word_budget"],
            )
            assert adaptive["body_word_budget"] >= 1


def test_metrics_report_three_turn_dynamics_without_pooling_modes():
    row = {
        "condition_id": "baseline_high",
        "opposing_judgment": "no violation",
        "initial_score": 80,
        "turns": [{"score": 70}, {"score": 20}, {"score": 30}],
    }
    report = metrics([row], 3)["baseline_high"]
    assert report["turn_count"] == 3
    assert report["persuasion_rate_by_turn"] == [0, 1, 1]
    assert report["any_turn_persuasion_rate"] == 1
    assert report["final_turn_persuasion_rate"] == 1
    assert report["first_persuasion_turn_counts"] == {"2": 1}


def test_assessment_parser_is_import_safe_and_strict():
    score, explanation = parse_assessment(assessment(73))
    assert score == 73
    assert explanation == "One concise reason."
