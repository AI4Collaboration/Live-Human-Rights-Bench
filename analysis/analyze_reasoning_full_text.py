"""Full-explanation analysis of saved reasoning, without word-length cutoffs.

No model calls. Cue comparisons retain the existing complete-conversation
cohorts. Paired length comparisons additionally require readable reasoning
under every compared cue, and report that availability filter explicitly.
"""
from pathlib import Path
import argparse
import collections
import csv
import gzip
import hashlib
import json
import re
import subprocess

import numpy as np

from analyze_reasoning_language import CUES, PATTERNS, RX
from analyze_reasoning_traces import complete, identity, opposite, verdict

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis/reasoning_traces/full_text"
WORD = re.compile(r"\b\w+(?:['’]\w+)?\b")
BOOTSTRAP_DRAWS = 5000
SEED = 20260926
LABELS = {"baseline_high": "No cue", "authority_lawyer": "Lawyer",
          "authority_researcher": "AI safety researcher"}


def count_spans(text, patterns=RX):
    merged = []
    for start, end in sorted((m.start(), m.end()) for rx in patterns.values()
                             for m in rx.finditer(text)):
        if merged and start < merged[-1][1]:
            merged[-1][1] = max(end, merged[-1][1])
        else:
            merged.append([start, end])
    return len(merged)


def measure(row, turn):
    text = row.get("reasoning", [])[turn] if len(row.get("reasoning", [])) > turn else ""
    words = len(WORD.findall(text))
    count = count_spans(text)
    strict = count_spans(text, {k: v for k, v in RX.items() if k != "behavior_test"})
    score = row["scores"][turn]
    initial = verdict(row["initial_score"])
    current = verdict(score)
    return dict(item_id=row["item_id"], article_full=str(row["article_full"]),
                words=words, occurrences=count, mentioned=count > 0,
                strict_mentioned=strict > 0, reversed=opposite(row, score),
                retained=current == initial, abstained=current == "abstain",
                initial_correct=initial == row["violation_label"],
                correct=current == row["violation_label"],
                initial_score=row["initial_score"], score=score,
                text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest())


def describe(records):
    readable = [r for r in records if r["words"] > 0]
    lengths = np.array([r["words"] for r in readable], dtype=float)
    mentioned = [r for r in readable if r["mentioned"]]
    other = [r for r in readable if not r["mentioned"]]
    strict = [r for r in readable if r["strict_mentioned"]]
    occurrences = sum(r["occurrences"] for r in readable)
    total_words = int(lengths.sum())
    def outcomes(rows):
        n = len(rows)
        return dict(n=n, reversed=sum(r["reversed"] for r in rows),
                    retained=sum(r["retained"] for r in rows),
                    abstained=sum(r["abstained"] for r in rows),
                    initially_correct=sum(r["initial_correct"] for r in rows),
                    reversal_pct=100 * sum(r["reversed"] for r in rows) / n if n else None)
    return dict(n=len(records), nonempty_n=len(readable), empty_n=len(records)-len(readable),
                median_words=float(np.median(lengths)) if len(lengths) else None,
                q25_words=float(np.quantile(lengths, .25)) if len(lengths) else None,
                q75_words=float(np.quantile(lengths, .75)) if len(lengths) else None,
                mean_words=float(np.mean(lengths)) if len(lengths) else None,
                total_words=total_words, mentions_n=len(mentioned),
                mention_pct=100*len(mentioned)/len(readable) if readable else None,
                occurrences=occurrences,
                occurrences_per_1000_words=1000*occurrences/total_words if total_words else None,
                with_mentions=outcomes(mentioned), without_mentions=outcomes(other),
                self_reference_only=outcomes(strict))


def paired_comparison(keys, original, changed):
    """Resample source judgments and keep their targets and both cues together."""
    w0 = np.array([r["words"] for r in original], dtype=float)
    w1 = np.array([r["words"] for r in changed], dtype=float)
    c0 = np.array([r["occurrences"] for r in original], dtype=float)
    c1 = np.array([r["occurrences"] for r in changed], dtype=float)
    groups = collections.defaultdict(list)
    for i, key in enumerate(keys):
        groups[key[0]].append(i)
    blocks = [np.array(v, dtype=int) for v in groups.values()]
    sizes = np.array([len(b) for b in blocks])
    rng = np.random.default_rng(SEED)
    draws = rng.integers(0, len(blocks), size=(BOOTSTRAP_DRAWS, len(blocks)))
    medians, ratios, longer = [], [], []
    for draw in draws:
        ids = np.concatenate([blocks[i] for i in draw])
        medians.append(float(np.median(w1[ids] - w0[ids])))
        ratios.append(float(np.median(w1[ids]) / np.median(w0[ids])))
        longer.append(float(100*np.mean(w1[ids] > w0[ids])))
    def boot_sum(arr):
        totals = np.array([arr[b].sum() for b in blocks])
        return totals[draws].sum(axis=1)
    base_density = 1000*c0.sum()/w0.sum()
    changed_density = 1000*c1.sum()/w1.sum()
    b0 = 1000*boot_sum(c0)/boot_sum(w0)
    b1 = 1000*boot_sum(c1)/boot_sum(w1)
    rate_diff = 100*(boot_sum(c1 > 0)-boot_sum(c0 > 0))/sizes[draws].sum(axis=1)
    interval = lambda a: [float(v) for v in np.quantile(a, [.025, .975])]
    return dict(n=len(keys), judgments=len(blocks),
                original_median_words=float(np.median(w0)), changed_median_words=float(np.median(w1)),
                ratio_of_medians=float(np.median(w1)/np.median(w0)), ratio_of_medians_ci95=interval(ratios),
                median_paired_word_change=float(np.median(w1-w0)),
                median_paired_word_change_ci95=interval(medians),
                longer_n=int((w1>w0).sum()), shorter_n=int((w1<w0).sum()), equal_n=int((w1==w0).sum()),
                longer_pct=float(100*np.mean(w1>w0)), longer_pct_ci95=interval(longer),
                original_occurrences_per_1000_words=float(base_density),
                changed_occurrences_per_1000_words=float(changed_density),
                density_ratio=float(changed_density/base_density) if base_density else None,
                density_difference=float(changed_density-base_density), density_difference_ci95=interval(b1-b0),
                mention_rate_difference_percent=float(100*np.mean((c1>0).astype(int)-(c0>0).astype(int))),
                mention_rate_difference_ci95=interval(rate_diff))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", default="8f8dcfabe95fdab402de8ad66005530fbc987ec7")
    args = parser.parse_args()
    revision = subprocess.check_output(["git", "rev-parse", args.revision], cwd=ROOT, text=True).strip()
    sources, summaries, paired_rows, paired, observations = {}, [], [], [], []
    all_conditions, cohorts, longitudinal = [], {}, []
    def read(path):
        raw = subprocess.check_output(["git", "show", f"{revision}:{path}"], cwd=ROOT)
        sources[path] = hashlib.sha256(raw).hexdigest()
        return raw
    released = {identity(r): r for r in json.loads(read("data/processed/echr_unified.json"))}
    for directory, model in [("syco_cot_opus", "Opus-4.6"), ("syco_cot", "V4-Flash")]:
        prefix = f"data/experiments/{directory}/"
        config = json.loads(read(prefix + "run_config.json"))
        initial = {identity(r): r for r in map(json.loads, read(prefix + "initial.jsonl").splitlines())}
        rows = list(map(json.loads, gzip.decompress(read(prefix + "trajectories.jsonl.gz")).splitlines()))
        assert len({(r["arm"], r["condition"], identity(r)) for r in rows}) == len(rows)
        for row in rows:
            key = identity(row)
            assert row["initial_score"] == initial[key]["initial_score"]
            assert row["violation_label"] == released[key]["violation_label"]
        for arm in ["static", "adaptive"]:
            arm_rows = [r for r in rows if r["arm"] == arm]
            for condition in sorted({r["condition"] for r in arm_rows}):
                selected = [r for r in arm_rows if r["condition"] == condition and complete(r)]
                for turn in range(3):
                    all_conditions.append(dict(model=model, mode=arm, cue=condition, turn=turn+1,
                                               published_n=sum(r["condition"] == condition for r in arm_rows),
                                               **describe([measure(r, turn) for r in selected])))
            index = {cue: {identity(r): r for r in arm_rows if r["condition"] == cue and complete(r)} for cue in CUES}
            common = sorted(set.intersection(*(set(index[c]) for c in CUES)))
            if not common:
                continue
            for key in common:
                assert len({index[c][key]["initial_score"] for c in CUES}) == 1
            measured = {c: {key: [measure(index[c][key], t) for t in range(3)] for key in common} for c in CUES}
            group_name = model + "/" + arm
            cohorts[group_name] = dict(complete_three_cue=common, paired_nonempty_by_turn={})
            all_turn_keys = [k for k in common if all(measured[c][k][t]["words"] > 0 for c in CUES for t in range(3))]
            cohorts[group_name]["paired_nonempty_all_turns"] = all_turn_keys
            for turn in range(3):
                available = [k for k in common if all(measured[c][k][turn]["words"] > 0 for c in CUES)]
                cohorts[group_name]["paired_nonempty_by_turn"][str(turn+1)] = available
                for cue in CUES:
                    values = [measured[cue][k][turn] for k in common]
                    summaries.append(dict(model=model, mode=arm, cue=cue, turn=turn+1, **describe(values)))
                    paired_values = [measured[cue][k][turn] for k in available]
                    paired_rows.append(dict(model=model, mode=arm, cue=cue, turn=turn+1, **describe(paired_values)))
                    longitudinal.append(dict(model=model, mode=arm, cue=cue, turn=turn+1,
                                             **describe([measured[cue][k][turn] for k in all_turn_keys])))
                    for r in values:
                        observations.append(dict(model=model, mode=arm, cue=cue, turn=turn+1, **r))
                if arm == "static" and turn == 0:
                    for cue in CUES[1:]:
                        paired.append(dict(model=model, mode=arm, cue=cue, turn=turn+1,
                                           **paired_comparison(available,
                                               [measured[CUES[0]][k][turn] for k in available],
                                               [measured[cue][k][turn] for k in available])))
    definitions = dict(
        scope="Entire saved explanation at each challenged turn; no prefix truncation or minimum length.",
        cohort="Complete three-turn scores under no cue, lawyer and AI safety researcher within each model and mode; initial responses are shared across these cues.",
        availability="Empty text is unavailable reasoning, not zero awareness. Report availability on the whole cohort and text rates among nonempty explanations.",
        paired="Paired cue comparisons retain instances with nonempty explanations under all three cues at that turn; there is no word-count cutoff.",
        longitudinal="Same instances with nonempty explanations for all three cues and all three turns, for within-model changes over turns.",
        length="Word counts use the published word regex. Median and interquartile range describe the complete explanation.",
        frequency="Explanations with at least one evaluation phrase divided by nonempty explanations; each instance counts once.",
        density="Nonoverlapping phrase occurrences divided by all words in the complete explanations, multiplied by 1000.",
        outcomes="Same-turn opposite decisive verdict among explanations containing the phrases; abstentions remain in this denominator. Text groups are descriptive and not randomized.",
        all_conditions="Condition-specific complete cohorts; for supplementary coverage only, not paired role effect estimates.",
        uncertainty="5000 source-judgment cluster bootstrap draws; target provisions and paired cues stay together; seed 20260926.",
        interpretation="Verbalized references to evaluation in written explanations, including Opus's summarized reasoning; not latent awareness or a causal mechanism.")
    report = dict(source_revision=revision, source_sha256=sources, word_rule=WORD.pattern,
                  phrase_rules=PATTERNS, definitions=definitions, model_api_calls=0,
                  rows=summaries, paired_rows=paired_rows, paired_comparisons=paired,
                  longitudinal_rows=longitudinal, all_condition_rows=all_conditions)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/"results.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    (OUT/"cohorts.json").write_text(json.dumps(cohorts, indent=2)+"\n", encoding="utf-8")
    with (OUT/"observations.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(observations[0]))
        writer.writeheader(); writer.writerows(observations)
    lines = ["# Full-explanation analysis", "", f"Source revision: `{revision}`. Existing data only; no model API calls.", "",
             "## Measures and cohorts", ""]
    lines += [f"- **{key.capitalize()}:** {value}" for key, value in definitions.items()]
    lines += ["", "## First static challenge: availability and full explanations", "",
              "| Model | Cue | Recorded / cohort | Median words [IQR] | Evaluation mentions | Occurrences / 1,000 words |",
              "|---|---|---:|---:|---:|---:|"]
    for r in summaries:
        if r["mode"] == "static" and r["turn"] == 1:
            lines.append(f"| {r['model']} | {LABELS[r['cue']]} | {r['nonempty_n']}/{r['n']} | {r['median_words']:g} [{r['q25_words']:g}, {r['q75_words']:g}] | {r['mentions_n']}/{r['nonempty_n']} ({r['mention_pct']:.1f}%) | {r['occurrences_per_1000_words']:.3f} |")
    lines += ["", "## First static challenge: same instances with text in all three cues", "",
              "| Model | Cue | N | Median words [IQR] | Evaluation mentions | Occurrences / 1,000 words |",
              "|---|---|---:|---:|---:|---:|"]
    for r in paired_rows:
        if r["mode"] == "static" and r["turn"] == 1:
            lines.append(f"| {r['model']} | {LABELS[r['cue']]} | {r['n']} | {r['median_words']:g} [{r['q25_words']:g}, {r['q75_words']:g}] | {r['mentions_n']}/{r['n']} ({r['mention_pct']:.1f}%) | {r['occurrences_per_1000_words']:.3f} |")
    lines += ["", "## Text and judgment changes", "", "This comparison uses the same first-turn instances with text under all three cues as the paired table above.", "",
              "| Model | Cue | Reversal among explanations mentioning evaluation | Reversal among explanations without such mentions |",
              "|---|---|---:|---:|"]
    for r in paired_rows:
        if r["mode"] == "static" and r["turn"] == 1:
            a,b=r['with_mentions'],r['without_mentions']
            lines.append(f"| {r['model']} | {LABELS[r['cue']]} | {a['reversed']}/{a['n']} ({a['reversal_pct']:.1f}%) | {b['reversed']}/{b['n']} ({b['reversal_pct']:.1f}%) |")
    lines += ["", "`results.json` includes all three turns, adaptive coverage, paired intervals and a separate all-condition inventory. `cohorts.json` lists exact target identities. `observations.csv` records full-text counts, verdict categories and hashes without reproducing the explanations.", "",
              "## Reproduction", "", f"`python analysis/analyze_reasoning_full_text.py --revision {revision}`", "",
              "Every recorded explanation is analyzed in full; cue comparisons require available text without a minimum word count.", ""]
    (OUT/"README.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(dict(source_revision=revision, observations=len(observations),
                          primary=[r for r in paired_rows if r['mode']=='static' and r['turn']==1],
                          paired_comparisons=paired), indent=2))


if __name__ == "__main__":
    main()
