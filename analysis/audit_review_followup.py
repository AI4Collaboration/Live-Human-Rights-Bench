"""Verify current input texts against their released review registry, offline."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'analysis/review_followup/input_evidence.json'


def blob(path):
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', 'HEAD:' + path])


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    names = {
        'dataset': 'data/processed/echr_unified.json',
        'summaries': 'data/processed/summaries_dsv41flash.json',
        'registry': 'data/audits/leakage_20260915/repair_release_report.json',
        'residual_review': 'data/audits/leakage_20260915/residual_assertion_context_review.json',
        'postcut_review': 'data/audits/verdict_spans/postcut_verification_20260916.json',
    }
    raw = {key: blob(path) for key, path in names.items()}
    data = {key: json.loads(value) for key, value in raw.items()}
    registry = data['registry']['input_registry']
    sources = {}
    for row in data['dataset']:
        key = row['item_id']
        text = row['full_case_text_no_verdict'][:50000]
        if key in sources:
            assert sources[key] == text, key
        sources[key] = text
    summaries = data['summaries']['summaries']
    assert set(sources) == set(summaries) == set(registry)
    source_mismatch = [key for key, value in sources.items()
                       if sha(value.encode()) != registry[key]['source_input_sha256']]
    summary_mismatch = [key for key, value in summaries.items()
                        if len(value) != 1 or sha(value[0].encode()) != registry[key]['summary_sha256']]
    assert not source_mismatch and not summary_mismatch
    report = {
        'status': 'pass', 'new_model_calls': 0,
        'method': 'Exact text-hash binding to existing source and summary review records; no new semantic or pretraining-contamination audit.',
        'targets': len(data['dataset']), 'judgments': len(sources),
        'source_character_cap': 50000,
        'source_input_hash_mismatches': source_mismatch,
        'selected_summary_hash_mismatches': summary_mismatch,
        'review_scope': data['registry']['scope'],
        'existing_lexical_context_review': {
            key: data['residual_review'][key] for key in
            ('matches', 'judgments', 'unresolved_current_case_assertions_in_these_matches', 'scope')
        },
        'source_files': {key: {'path': names[key], 'sha256_git_blob': sha(value)}
                         for key, value in raw.items()},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f'Bound {len(sources)} sources and selected summaries to released review evidence; zero mismatches.')


if __name__ == '__main__':
    main()
