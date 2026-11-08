"""Build the rebuttal evidence note and two manuscript tables from audited CSVs."""
from pathlib import Path
import argparse
import csv
import json

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "analysis/rebuttal_20261107"
NAMES = {"anthropic/claude-opus-4.6": "Opus-4.6", "openai/gpt-5.6-sol": "5.6-Sol",
         "deepseek/deepseek-v4-flash": "V4-Flash"}


def records(name):
    with (BASE / "new_controls" / name).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def pct(value):
    return f"{float(value):.1f}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper", type=Path)
    args = parser.parse_args()
    audit = json.loads((BASE / "new_controls/audit.json").read_text())
    spend = json.loads((BASE / "new_controls/spend.json").read_text())
    contrasts = [r for r in records("paired_contrasts.csv") if r["turn"] == "3"]
    repeat = records("repetition_variation.csv")
    parts = ["# Rebuttal analyses", "", "All new experiments use the frozen 50-judgment sample. The remaining analyses use existing records.", "",
             "## Opposing opinions have an effect beyond neutral reassessment", "",
             "These opinions assert the opposite verdict without asking for a changed answer. The formatting request is identical in every condition.", "",
             "| Model | Shared cases | Neutral reassessment | Opinion only |", "| --- | ---: | ---: | ---: |"]
    for r in contrasts:
        if r["control"] == "neutral_reassessment":
            n = r["paired_n"]
            parts.append(f"| {NAMES[r['model']]} | {n} | {r['control_reversed_n']}/{n} ({pct(r['control_pct'])}%) | {r['treatment_reversed_n']}/{n} ({pct(r['treatment_pct'])}%) |")
    parts += ["", "Challenges containing explicit demands to adopt the opposite verdict produce higher reversal rates. On the separately paired directive-versus-opinion cohorts the rates are 90.0% versus 26.0% for Opus-4.6, 89.6% versus 29.2% for 5.6-Sol, and 100.0% versus 58.5% for V4-Flash. Those comparisons use 50, 48 and 41 cases respectively. The contrast removes the replacement demand together with its confrontational wording. It separates opinion-only reversals from those under the original directive-containing challenge without isolating a training mechanism.", "",
              "## Evaluation wording changes 5.6-Sol's response with identity held fixed", "",
              "Both conditions introduce the challenger as an AI researcher. Only a six-word first-turn sentence changes.", "",
              "| Model | Shared cases | Neutral framing | Evaluation framing | Difference in reversal rate [95% interval] |",
              "| --- | ---: | ---: | ---: | ---: |"]
    for r in contrasts:
        if r["control"] == "ai_researcher_neutral":
            n = r["paired_n"]
            parts.append(f"| {NAMES[r['model']]} | {n} | {r['control_reversed_n']}/{n} ({pct(r['control_pct'])}%) | {r['treatment_reversed_n']}/{n} ({pct(r['treatment_pct'])}%) | {pct(r['delta_pct'])} [{pct(r['lo'])}, {pct(r['hi'])}] |")
    parts += ["", "Differences subtract the two rates expressed as percentages. The explicit evaluation sentence reduces reversal for 5.6-Sol. Opus-4.6 is already at 1/50 under neutral framing, leaving little room for a reduction. V4-Flash remains highly reversible. The Opus result is a floor observation, not evidence that evaluation awareness is absent. This intervention establishes sensitivity to evaluation wording, not a latent causal mechanism.", "",
              "## Repetitions preserve the cue ordering but reveal case-level variation", "",
              "The same initial reply starts three independent conversations per reference condition. The complete comparison requires all six conversations for a case.", "",
              "| Model | Cue | Cases | Final reversal in repeats 1 / 2 / 3 | Mean | Cases with different reversal outcomes |",
              "| --- | --- | ---: | ---: | ---: | ---: |"]
    for r in repeat:
        rates = " / ".join(pct(x) for x in json.loads(r["repetition_rates_pct"]))
        cue = "No cue" if r["condition"] == "no_cue" else "AI safety researcher"
        parts.append(f"| {NAMES[r['model']]} | {cue} | {r['paired_cases']} | {rates}% | {pct(r['mean_reversal_pct'])}% | {r['mixed_reversal_cases']}/{r['paired_cases']} ({pct(r['mixed_reversal_pct'])}%) |")
    parts += ["", "The Opus comparison contains 144 trajectories per condition and the Sol comparison contains 147. Three identical aggregate no-cue rates for Sol still hide changes in which five cases reverse. The researcher cue changes the reversal outcome across repeats for 11 of 49 Sol cases. Large average cue effects therefore coexist with instance-level sampling variability. The intervals in `new_controls/repetition_variation.csv` resample cases and then repetitions; they do not treat trajectories as independent new cases.", "",
              "## The paraphrase result survives a fact-preservation filter", "",
              "An independent Qwen3-235B verifier checks 69,106 claim-target pairs. Repaired paraphrases retain 99.2–99.5% of originally supported sampled claims. The verifier rejects 256 of 300 controls with deliberately swapped attributes. Without looking at target-model outcomes, we select 540 targets from 521 judgments where all sampled claims supported in the original remain supported in every rewrite. The selected targets have a median of 76 supported claims. Judgment-change rates remain 4.8–15.4% across the five primary models and three strengths. The filter covers sampled claims; it is not a human certification of the entire text.", "",
              "Exact counts, intervals and missing-score counts are in [paraphrase_sensitivity.csv](existing/paraphrase_sensitivity.csv). Accuracy and change use the same target denominator within each scope. The 1,000-target repaired analysis and this 540-target sensitivity are separate.", "",
              "## Reasoning evidence remains descriptive", "",
              "The full-text analysis measures expressed references to evaluation. In the existing reasoning run, V4-Flash reverses in 125/201 researcher-cue explanations that mention evaluation. Opus also has nonrandom text availability: all 177 first-turn no-cue responses without explanations reverse, compared with 653/734 with explanations. Paired language comparisons retain the same cases with available text across cues. These processed explanations do not establish why a judgment changes.", "",
              "## Release checks and the remaining empirical gap", "",
              "All three designated v1.0 input hashes match the frozen release manifest. An offline chronological reconstruction merges 943 pre-2026 targets with the 57 v1.0 targets from 2026 and preserves every earlier record. This verifies existing-release consistency. Evaluation of genuinely new judgments remains a [separate task](../../docs/rebuttal/DELEGATED_TASKS.md).", "",
              "## Coverage, cost and reproducibility", "",
              f"All 1,300 planned trajectories were attempted. There are {audit['recorded_calls']:,} recorded requests and {audit['complete_trajectories']:,} complete three-turn trajectories. Twenty-six requests have no parsed score, including three timeouts. Later calls after an empty or failed reply were not sent. Incomplete trajectories are retained in the released records and excluded only from their explicitly defined comparisons. Missing-case bounds appear in `new_controls/condition_rates.csv`.", "",
              f"The key's observed usage increased by **${spend['observed_usage_delta_usd']:.2f}**. Successful responses report ${audit['reported_cost_usd']:.6f}; the local ledger charges ${audit['conservative_charge_usd']:.6f} after conservatively reserving for timeouts. The execution ceiling was $50. No more paid experiments are scheduled in this package.", "",
              f"The audit passed {audit['integrity_checks']:,} checks against saved messages and responses. It verifies initial replay, target identity, prompt hashes, score parsing, decoding requests and unique call IDs. The [protocol](../../docs/rebuttal/EXPERIMENTS.md) and [raw run](../../data/experiments/rebuttal_20261107/) retain the full collection record.", "",
              "```bash", "python analysis/analyze_rebuttal_existing.py", "python analysis/analyze_rebuttal_controls.py", "python analysis/build_rebuttal_report.py", "```", ""]
    (BASE / "REPORT.md").write_text("\n".join(parts), encoding="utf-8")
    if args.paper:
        tables = args.paper / "tables"
        lines = [r"\begin{table}[htp]", r"\centering", r"\small",
            r"\caption{\textbf{Repeated conversations preserve large cue effects while individual outcomes can vary.} Each rate comes from an independent three-turn static conversation with the same saved initial reply. $N$ counts judgments complete in all three repetitions under both conditions. Researcher means AI safety researcher. The last column gives the share whose reversal outcome differs across repetitions under no cue / researcher.}",
            r"\label{tab:rebuttal_repetitions}", r"\begin{tabular}{lrrrl}", r"\toprule",
            r"Model & $N$ & No cue (\%) & Researcher (\%) & Varying (\%) \\", r"\midrule"]
        for m in list(NAMES)[:2]:
            a, b = [next(r for r in repeat if r["model"] == m and r["condition"] == c) for c in ("no_cue", "safety_researcher")]
            ra, rb = [" / ".join(pct(x) for x in json.loads(r["repetition_rates_pct"])) for r in (a,b)]
            lines.append(f"{NAMES[m]} & {a['paired_cases']} & {ra} & {rb} & {pct(a['mixed_reversal_pct'])} / {pct(b['mixed_reversal_pct'])} \\\\")
        lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
        (tables / "rebuttal_repetitions.tex").write_text("\n".join(lines), encoding="utf-8")
        lines = [r"\begin{table}[htp]", r"\centering", r"\small",
            r"\caption{\textbf{Models respond differently to opposition and evaluation wording.} Each row compares the same $N$ judgments with three valid scores in both conditions out of 50 planned judgments. Rates concern the final turn. The no-cue reference uses the first repetition. Differences subtract the control rate from the test rate; brackets give 95\% paired case-bootstrap intervals. Both framing conditions retain the AI researcher role and differ in one six-word sentence.}",
            r"\label{tab:rebuttal_controls}", r"\begin{tabular}{lrrrr}", r"\toprule",
            r"Model & $N$ & Control (\%) & Test (\%) & Difference [95\% interval] \\", r"\midrule"]
        for a,b,label in [("no_cue","opinion_only","(a) Replacement directive to opinion only"),
                          ("neutral_reassessment","opinion_only","(b) Neutral reassessment to opinion only"),
                          ("ai_researcher_neutral","ai_researcher_evaluation","(c) AI researcher: neutral to evaluation wording")]:
            lines.append(r"\multicolumn{5}{l}{\textit{" + label + r"}} \\")
            for m in NAMES:
                r=next(r for r in contrasts if r["model"]==m and r["control"]==a and r["treatment"]==b)
                lines.append(f"{NAMES[m]} & {r['paired_n']} & {pct(r['control_pct'])} & {pct(r['treatment_pct'])} & ${pct(r['delta_pct'])}$ [$ {pct(r['lo'])}, {pct(r['hi'])} $] \\\\")
            lines.append(r"\midrule")
        lines[-1]=r"\bottomrule"
        lines += [r"\end{tabular}", r"\end{table}", ""]
        (tables / "rebuttal_controls.tex").write_text("\n".join(lines), encoding="utf-8")
        lines = [r"\begin{table}[tp]", r"\centering", r"\small",
            r"\caption{\textbf{Opposition raises reversal while evaluation wording reduces it in 5.6-Sol.} Each row compares the same $N$ cases with complete three-turn conversations in both conditions. The initial reply is fixed. Rates are final-turn reversals; neither condition adds case evidence. Appendix Table~\ref{tab:rebuttal_controls} gives paired intervals and the separate comparison with replacement demands.}",
            r"\label{tab:targeted_controls_main}", r"\begin{tabular}{lrrr}", r"\toprule",
            r"Model & $N$ & Control (\%) & Test (\%) \\", r"\midrule"]
        for a,b,label in [("neutral_reassessment","opinion_only","(a) Neutral reassessment versus opposing opinion"),
                          ("ai_researcher_neutral","ai_researcher_evaluation","(b) AI researcher: neutral versus evaluation wording")]:
            lines.append(r"\multicolumn{4}{l}{\textit{" + label + r"}} \\")
            for m in NAMES:
                r=next(r for r in contrasts if r["model"]==m and r["control"]==a and r["treatment"]==b)
                lines.append(f"{NAMES[m]} & {r['paired_n']} & {pct(r['control_pct'])} & {pct(r['treatment_pct'])} \\\\")
            lines.append(r"\midrule")
        lines[-1]=r"\bottomrule"
        lines += [r"\end{tabular}", r"\end{table}", ""]
        (tables / "rebuttal_controls_main.tex").write_text("\n".join(lines), encoding="utf-8")
    print("Built evidence report" + (" and three manuscript tables." if args.paper else "."))


if __name__ == "__main__":
    main()
