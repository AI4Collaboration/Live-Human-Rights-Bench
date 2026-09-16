"""Immutable run settings for matched, single-summary perturbation rescoring."""
import json
from pathlib import Path

SUMMARY_PROTOCOL = "one-summary-per-judgment"
SCORING = {"scale": [0, 100], "violation_above": 60, "no_violation_below": 40,
           "aggregation": "most-frequent-category; ties abstain"}


def bind_run_config(directory, config):
    """Do not mix models, sample counts, prompts or scoring rules on resume."""
    if (config.get("summary_protocol") != SUMMARY_PROTOCOL or config.get("scoring") != SCORING
            or isinstance(config.get("samples"), bool) or not isinstance(config.get("samples"), int)
            or config["samples"] < 1):
        raise ValueError("Invalid single-summary run configuration")
    directory = Path(directory)
    path = directory / "run_config.json"
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != config:
            raise ValueError("Run settings changed; use a new result directory")
    else:
        if any(directory.glob("*_results.json")) or any(directory.glob("*.jsonl")):
            raise ValueError("Unversioned results cannot be relabeled as a new rescore")
        directory.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return config


def complete_samples(row, count=None):
    """API failures are incomplete work, not predictions or abstentions."""
    if row is None:
        return False
    fields = ("original_ratings", "challenged_ratings") if "original_ratings" in row else ("ratings",)
    for field in fields:
        values = row.get(field)
        if (not isinstance(values, list) or not values or (count is not None and len(values) != count)
                or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 100 for v in values)):
            return False
    return True
