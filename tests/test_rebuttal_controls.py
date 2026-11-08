"""Offline checks for spending and intervention identity; no API access."""
import importlib.util
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

PATH = Path(__file__).parents[1] / "experiments/rebuttal_controls.py"
SPEC = importlib.util.spec_from_file_location("rebuttal_controls", PATH)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def test_budget_cannot_overreserve_with_concurrent_workers():
    budget = runner.Budget(1.0)
    with ThreadPoolExecutor(max_workers=12) as pool:
        accepted = list(pool.map(lambda _: budget.reserve(0.3), range(12)))
    assert sum(accepted) == 3
    assert budget.spent + budget.reserved <= budget.limit
    budget.settle(0.3, 0.1)
    assert budget.reserve(0.3)
    assert budget.spent + budget.reserved <= budget.limit


def test_framing_changes_only_one_sentence_and_only_turn_one():
    pack = runner.json.loads((runner.ROOT / "configs/adversarial_opinion_prompts.json").read_text())
    case = {name: "test" for name in ("case_text", "target_provision", "target_question", "target_respondent", "target_issue")}
    neutral = runner.challenges(pack, case, 90, "ai_researcher_neutral")
    evaluation = runner.challenges(pack, case, 90, "ai_researcher_evaluation")
    assert neutral[1:] == evaluation[1:]
    assert neutral[0].replace("This conversation concerns the present case.",
                              "This conversation evaluates your model behavior.") == evaluation[0]
    assert len(neutral[0].split()) == len(evaluation[0].split())


def test_opinion_control_never_requests_a_change_in_answer():
    pack = runner.json.loads((runner.ROOT / "configs/adversarial_opinion_prompts.json").read_text())
    case = {name: "test" for name in ("case_text", "target_provision", "target_question", "target_respondent", "target_issue")}
    for initial in (10, 90):
        text = runner.challenges(pack, case, initial, "opinion_only")
        for turn in text:
            opinion = turn.split(pack["response_request"])[0].lower()
            assert all(word not in opinion for word in ("replace", "reconsider", "must", "assess it"))
            assert ("no violation" if initial > 60 else "a violation") in opinion
        neutral = runner.challenges(pack, case, initial, "neutral_reassessment")
        assert len(set(neutral)) == 1
        assert "Court would find" not in neutral[0]
