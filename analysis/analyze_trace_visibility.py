"""Offline analysis of released reasoning text only: coverage, length and phrases.

Complete score trajectories define the existing comparison cohort; no verdict,
accuracy, reversal or correctness statistic enters this analysis.
"""
from pathlib import Path
import collections
import csv
import gzip
import hashlib
import json
import re
import subprocess

import numpy as np

from analyze_reasoning_language import CUES, RX, PATTERNS, REVISION
from analyze_reasoning_traces import complete, identity

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis/reasoning_traces/visibility"
WORD = re.compile(r"\b\w+(?:['’]\w+)?\b")


def spans(text):
    merged = []
    for start, end in sorted((m.start(), m.end()) for rx in RX.values() for m in rx.finditer(text)):
        if merged and start < merged[-1][1]:
            merged[-1][1] = max(end, merged[-1][1])
        else:
            merged.append([start, end])
    return merged


def describe(texts):
    lengths = np.array([len(WORD.findall(t)) for t in texts])
    occurrences = [len(spans(t)) for t in texts]
    nonempty = lengths > 0
    return dict(n=len(texts), empty_n=int((~nonempty).sum()),
        nonempty_n=int(nonempty.sum()), median_words_nonempty=float(np.median(lengths[nonempty])),
        visible_words=int(lengths.sum()), matching_traces=sum(n > 0 for n in occurrences),
        matching_pct_nonempty=100*sum(n > 0 for n in occurrences)/int(nonempty.sum()),
        nonoverlapping_phrase_occurrences=sum(occurrences),
        occurrences_per_1000_words=1000*sum(occurrences)/int(lengths.sum()))


def paired_interval(keys, differences):
    groups = collections.defaultdict(list)
    for key, difference in zip(keys, differences):
        groups[key[0]].append(difference)
    groups = list(groups.values())
    sums = np.array([sum(g) for g in groups]); sizes = np.array([len(g) for g in groups])
    draw = np.random.default_rng(20260926).integers(0, len(groups), (5000, len(groups)))
    boot = 100*sums[draw].sum(axis=1)/sizes[draw].sum(axis=1)
    return [float(v) for v in np.quantile(boot, [.025, .975])]


def main():
    sources, by_model, rows, keys_seen = {}, {}, [], set()
    for directory, model in [("syco_cot_opus", "Opus-4.6"), ("syco_cot", "V4-Flash")]:
        path = f"data/experiments/{directory}/trajectories.jsonl.gz"
        raw = subprocess.check_output(["git", "show", f"{REVISION}:{path}"], cwd=ROOT)
        sources[path] = hashlib.sha256(raw).hexdigest()
        records = [json.loads(line) for line in gzip.decompress(raw).splitlines()]
        keys_seen.update(k for row in records for k in row)
        index = {cue: {identity(r): r["reasoning"][0] if r["reasoning"] else ""
                      for r in records if r["arm"] == "static" and r["condition"] == cue and complete(r)}
                 for cue in CUES}
        common = set.intersection(*(set(index[c]) for c in CUES))
        by_model[model] = {cue: {key: index[cue][key] for key in sorted(common)} for cue in CUES}
        for cue in CUES:
            rows.append(dict(model=model, cue=cue, **describe(list(by_model[model][cue].values()))))
    shared = sorted(set.intersection(*(set(v) for cues in by_model.values() for v in cues.values())))
    windows, cohorts = [], {}
    for length in [64, 128, 256]:
        keys = [key for key in shared if all(len(WORD.findall(by_model[m]["authority_researcher"][key])) >= length
                                            for m in by_model)]
        cohorts[str(length)] = keys
        model_rows, full, prefix = {}, {}, {}
        for model in by_model:
            texts = [by_model[model]["authority_researcher"][key] for key in keys]
            prefixes = [t[:list(WORD.finditer(t))[length-1].end()] for t in texts]
            full[model] = np.array([bool(spans(t)) for t in texts], dtype=int)
            prefix[model] = np.array([bool(spans(t)) for t in prefixes], dtype=int)
            model_rows[model] = dict(full_matching=int(full[model].sum()), prefix_matching=int(prefix[model].sum()),
                full_pct=float(full[model].mean()*100), prefix_pct=float(prefix[model].mean()*100))
        gap_full = full["V4-Flash"]-full["Opus-4.6"]
        gap_prefix = prefix["V4-Flash"]-prefix["Opus-4.6"]
        windows.append(dict(words=length, n=len(keys), judgments=len({key[0] for key in keys}), models=model_rows,
            full_gap_pp=float(gap_full.mean()*100), prefix_gap_pp=float(gap_prefix.mean()*100),
            full_gap_ci95=paired_interval(keys, gap_full), prefix_gap_ci95=paired_interval(keys, gap_prefix),
            gap_reduction_pp=float((gap_full-gap_prefix).mean()*100),
            gap_reduction_ci95=paired_interval(keys, gap_full-gap_prefix)))
    path = "experiments/syco_cot_run.py"
    raw = subprocess.check_output(["git", "show", f"{REVISION}:{path}"], cwd=ROOT)
    sources[path] = hashlib.sha256(raw).hexdigest()
    report = dict(source_revision=REVISION, source_sha256=sources, keyword_rules=PATTERNS,
        word_rule=WORD.pattern, model_specific_rows=rows, six_condition_shared_n=len(shared), paired_windows=windows,
        metadata_audit=dict(saved_record_keys=sorted(keys_seen), raw_provider_blocks_saved=False,
            redaction_block_types_saved=False, timestamps_saved=False, raw_unsummarized_counterpart_available=False,
            attribution="These records cannot identify a censorship or summarization-policy change."),
        definitions=dict(text_frequency="At least one phrase match divided by nonempty traces; each target counts once.",
            density="Nonoverlapping phrase occurrences per 1000 visible word tokens; overlapping rule matches merged.",
            prefix="Researcher cue only. Same targets in both models; both complete all three cue conversations and contain at least K words. All comparisons use exactly the first K words.",
            selection="K-specific eligible subsets; comparisons across K are not the same population. Original text is retained for the full versus prefix comparison within each K.",
            interpretation="Prefix truncation is a sensitivity analysis of text exposure and keyword position. It does not reproduce provider summarization or safety redaction."))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/"results.json").write_text(json.dumps(report, indent=2)+"\n")
    (OUT/"prefix_cohorts.json").write_text(json.dumps(cohorts, indent=2)+"\n")
    with (OUT/"counts.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    lines = ["# Reasoning-text visibility and keyword frequency", "", f"Source: `{REVISION}`. No model API calls.", "",
        "This analysis uses only returned reasoning text. It does not report judgment changes or accuracy.", "",
        "## Visible text and phrase frequency", "",
        "| Model | Cue | Empty / N | Median visible words, nonempty | Phrase-bearing / nonempty | Occurrences / 1000 words |",
        "|---|---|---:|---:|---:|---:|"]
    for row in rows:
        lines.append(f"| {row['model']} | {row['cue']} | {row['empty_n']}/{row['n']} | {row['median_words_nonempty']:g} | {row['matching_traces']}/{row['nonempty_n']} | {row['occurrences_per_1000_words']:.3f} |")
    lines += ["", "## Same-case, equal-window comparison", "",
        "All windows use the researcher cue. Both models must have at least K words; the eligible subset changes with K. The full-text and prefix comparison within each row always uses the same cases.", "",
        "| Visible prefix | N | Opus full / prefix | Flash full / prefix | Full / prefix Flash-minus-Opus gap (pp) |",
        "|---|---:|---:|---:|---:|"]
    for r in windows:
        op, fl = r['models']['Opus-4.6'], r['models']['V4-Flash']
        lines.append(f"| {r['words']} words | {r['n']} | {op['full_matching']}/{op['prefix_matching']} | {fl['full_matching']}/{fl['prefix_matching']} | {r['full_gap_pp']:.1f}/{r['prefix_gap_pp']:.1f} |")
    lines += ["", "Counts are literal phrase detections, not measures of latent evaluation awareness. Prefix truncation measures sensitivity to the analyzed text window; it does not emulate a provider's summary or redaction policy.", "",
        "## Provider policy and saved-data limits", "",
        "Anthropic documents summarized thinking for Opus 4.6 and the possibility of safety-redacted blocks. The saved runner keeps readable strings but drops raw provider block metadata. No timestamps, paired raw thinking or redaction-event indicators were saved, so these data cannot establish a policy change or count censorship events. Empty text is recorded as unavailable text, not as proven redaction.", "",
        "Provider documentation: [Thinking](https://platform.claude.com/docs/en/build-with-claude/thinking). Retrieved and checked on 2026-09-26.", "",
        "## Reproduction", "", "`python analysis/analyze_trace_visibility.py`", "",
        "Rules, corpus counts, bootstrap intervals, exact word matching and cohort membership are released alongside this report. Cluster intervals use 5000 source-judgment bootstrap resamples with seed 20260926.", ""]
    (OUT/"README.md").write_text("\n".join(lines))
    print(json.dumps(dict(rows=rows, primary_window=windows[1], metadata=report['metadata_audit'])))


if __name__ == "__main__":
    main()
