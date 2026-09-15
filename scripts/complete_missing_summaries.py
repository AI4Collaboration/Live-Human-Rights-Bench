#!/usr/bin/env python3
"""Repair only the nine missing DeepSeek summary slots in the frozen 1,000 pool.

Dry-run is the default. --execute requires OPENROUTER_API_KEY (or the named
--api-key-env) and reuses build_summaries.summarise without changing its prompt,
model, sampling settings, rejection screen, or 50,000-character input cap.
Existing usable summaries are never regenerated or rescreened.
"""

import argparse
import copy
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from scripts.build_summaries import summarise  # noqa: E402
from experiments.summaries import SUMMARY_TEMPLATE, is_usable  # noqa: E402
from experiments.scoring import MAX_CASE_CHARS  # noqa: E402

MODEL = "deepseek/deepseek-v4.1-flash"
BASE_URL = "https://openrouter.ai/api/v1"
EXPECTED_BASE_SUMMARIES_SHA256 = "fbe0f38934a951e5dbefa386b3bb0d168f5b497a930b3cf78079f7cff6c30f73"
EXPECTED_DATA_SHA256 = "d44e0eecc9f167f6868e79665ded075834a827df05d9d0afe0f14938d3ba8e35"
EXPECTED_MISSING = [
    ["001-166954", 2],
    ["001-219988", 0], ["001-219988", 1], ["001-219988", 2],
    ["001-223361", 1], ["001-229325", 0],
    ["001-231078", 0], ["001-231078", 1], ["001-238072", 0],
]


def sha256_lf(raw):
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def serialized(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(serialized(value))
    os.replace(temporary, path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def usable(value):
    return is_usable(value) and bool(value.strip())


def slot(mapping, item_id, version):
    return mapping.get(item_id, [None, None, None])[version]


def missing_slots(mapping, judgments):
    return [[item_id, version] for item_id in sorted(judgments)
            for version in range(3) if not usable(slot(mapping, item_id, version))]


def preserved_digest(mapping):
    excluded = {tuple(value) for value in EXPECTED_MISSING}
    original = [[item_id, version, value]
                for item_id in sorted(mapping)
                for version, value in enumerate(mapping[item_id])
                if (item_id, version) not in excluded]
    if len(original) != 2832 or not all(usable(row[2]) for row in original):
        raise ValueError("The 2,832 preserved summary slots are not intact")
    return sha256_lf(json.dumps(original, ensure_ascii=False).encode("utf-8"))


def now():
    return datetime.now(timezone.utc).isoformat()


def prepare(cases_path, summaries_path, manifest_path, checkpoint_path):
    data_raw = Path(cases_path).read_bytes()
    summary_raw = Path(summaries_path).read_bytes()
    if sha256_lf(data_raw) != EXPECTED_DATA_SHA256:
        raise ValueError("Frozen source dataset hash changed; refusing repair")
    cases, blob, manifest = json.loads(data_raw), json.loads(summary_raw), read_json(manifest_path)
    judgments = {}
    for case in cases:
        if case["item_id"] in judgments:
            continue
        source = case.get("full_case_text_no_verdict") or case.get("verdict_free_text") or ""
        judgments[case["item_id"]] = {
            "item_id": case["item_id"], "case_name": case["case_name"],
            "text": source[:MAX_CASE_CHARS],
        }
    if len(cases) != 1000 or len(judgments) != 947:
        raise ValueError("Expected exactly 1,000 instances and 947 judgments")
    if (blob.get("summarizer") != MODEL or blob.get("versions") != 3
            or blob.get("n_judgments") != 947):
        raise ValueError("Existing summary model/version/source contract differs")
    mapping = blob["summaries"]
    if not set(mapping) <= set(judgments) or any(len(v) != 3 for v in mapping.values()):
        raise ValueError("Summary IDs or slot counts differ from the frozen cohort")
    if (manifest["dataset"]["sha256_lf"] != EXPECTED_DATA_SHA256
            or manifest["summaries"]["summarizer"] != MODEL
            or manifest["summaries"]["versions"] != 3):
        raise ValueError("Manifest source/model contract differs")
    current_hash = sha256_lf(summary_raw)
    missing = missing_slots(mapping, judgments)
    untouched = preserved_digest(mapping)
    checkpoint_path = Path(checkpoint_path)
    if checkpoint_path.exists():
        checkpoint = read_json(checkpoint_path)
        if (checkpoint.get("schema_version") != 1
                or checkpoint.get("base_summaries_sha256_lf") != EXPECTED_BASE_SUMMARIES_SHA256
                or checkpoint.get("dataset_sha256_lf") != EXPECTED_DATA_SHA256
                or checkpoint.get("expected_missing_slots_zero_based") != EXPECTED_MISSING
                or checkpoint.get("preserved_summaries_sha256") != untouched):
            raise ValueError("Repair checkpoint does not match the original frozen artifacts")
        known_hashes = checkpoint["published_artifact_hashes"]
        if current_hash not in known_hashes or manifest["summaries"]["sha256_lf"] not in known_hashes:
            raise ValueError("Current summaries or manifest do not match this repair checkpoint")
    else:
        if (current_hash != EXPECTED_BASE_SUMMARIES_SHA256
                or manifest["summaries"]["sha256_lf"] != current_hash
                or missing != EXPECTED_MISSING):
            raise ValueError("Without a repair checkpoint, exactly the original nine slots must be missing")
        checkpoint = {
            "schema_version": 1, "created_utc": now(),
            "base_summaries_sha256_lf": EXPECTED_BASE_SUMMARIES_SHA256,
            "dataset_sha256_lf": EXPECTED_DATA_SHA256,
            "expected_missing_slots_zero_based": EXPECTED_MISSING,
            "preserved_summaries_sha256": untouched,
            "published_artifact_hashes": [current_hash],
            "generation": {"summarizer": MODEL, "base_url": BASE_URL,
                           "temperature": 1.0, "initial_max_tokens": 4000,
                           "attempts_per_call": 3, "max_case_chars": MAX_CASE_CHARS,
                           "prompt_template": SUMMARY_TEMPLATE},
            "historical_token_metadata": {key: blob.get(key) for key in
                                          ("prompt_tokens", "completion_tokens")},
            "attempts": [],
        }
    allowed = {tuple(value) for value in EXPECTED_MISSING}
    if len(missing) > 9 or any(tuple(value) not in allowed for value in missing):
        raise ValueError("Repair would extend beyond the nine authorized slots")
    successful = {}
    for attempt in checkpoint["attempts"]:
        key = (attempt["item_id"], attempt["version"])
        if key not in allowed:
            raise ValueError("Checkpoint contains an unauthorized slot")
        if attempt["accepted"]:
            if not usable(attempt["summary"]):
                raise ValueError("Checkpoint contains an invalid accepted summary")
            if key in successful and successful[key] != attempt["summary"]:
                raise ValueError("Checkpoint contains conflicting accepted summaries")
            successful[key] = attempt["summary"]
    for item_id, version in EXPECTED_MISSING:
        current = slot(mapping, item_id, version)
        if usable(current) and successful.get((item_id, version)) != current:
            raise ValueError("A repaired summary was modified outside this checkpoint")
    return judgments, blob, manifest, checkpoint, successful


def run(cases_path, summaries_path, manifest_path, checkpoint_path, *,
        execute=False, api_key_env="OPENROUTER_API_KEY", client_factory=None, workers=1):
    if not 1 <= workers <= 4:
        raise ValueError("Repair workers must be between 1 and 4")
    judgments, original, manifest, checkpoint, successful = prepare(
        cases_path, summaries_path, manifest_path, checkpoint_path)
    initial_summary_hash = sha256_lf(Path(summaries_path).read_bytes())
    initial_manifest_hash = sha256_lf(Path(manifest_path).read_bytes())
    units = [(item_id, version) for item_id, version in EXPECTED_MISSING
             if (item_id, version) not in successful]
    print(f"Frozen cohort: 1,000 instances / 947 judgments; preserved summaries: 2,832")
    print(f"Missing-summary calls scheduled: {len(units)} (hard limit: 9)")
    for item_id, version in units:
        print(f"  {item_id} version {version}")
    if not execute:
        print("Dry run only. Use --execute to generate these slots with the original DeepSeek method.")
        return 0
    if units:
        api_key = os.environ.get(api_key_env, "")
        if not api_key:
            raise ValueError(f"Set {api_key_env} before --execute; no calls or writes were made")
        if client_factory is None:
            from openai import OpenAI
            client_factory = OpenAI
        client = client_factory(base_url=BASE_URL, api_key=api_key)
    else:
        api_key = ""
        client = None
    atomic_json(checkpoint_path, checkpoint)
    def generate_units():
        with ThreadPoolExecutor(max_workers=workers) as pool:
            pending = {pool.submit(summarise, client, MODEL, judgments[item_id], 4000):
                       (item_id, version) for item_id, version in units}
            for future in as_completed(pending):
                item_id, version = pending[future]
                text, usage = future.result()
                yield item_id, version, text, usage

    for item_id, version, text, usage in generate_units():
        case = judgments[item_id]
        # Generation uses the original function; checkpoint writes stay serialized.
        accepted = usable(text)
        if not accepted and isinstance(text, str) and api_key:
            text = text.replace(api_key, "[REDACTED]")
        checkpoint["attempts"].append({
            "item_id": item_id, "version": version, "time_utc": now(),
            "accepted": accepted, "summary": text, "usage": usage,
            "input_sha256": hashlib.sha256(case["text"].encode("utf-8")).hexdigest(),
            "prompt_sha256": hashlib.sha256(SUMMARY_TEMPLATE.format(
                case_name=case["case_name"], full_text=case["text"]).encode("utf-8")).hexdigest(),
        })
        if accepted:
            successful[(item_id, version)] = text
        atomic_json(checkpoint_path, checkpoint)
        print(f"  {item_id} version {version}: {'accepted' if accepted else 'still missing'}")
    updated = copy.deepcopy(original)
    for (item_id, version), value in successful.items():
        updated["summaries"].setdefault(item_id, [None, None, None])[version] = value
    if preserved_digest(updated["summaries"]) != checkpoint["preserved_summaries_sha256"]:
        raise ValueError("Existing summary text changed; refusing publication")
    # Historical token fields remain untouched. This repair's usage lives only in
    # the checkpoint and is not incorrectly presented as a lifetime corpus total.
    remaining = missing_slots(updated["summaries"], judgments)
    complete = sum(all(usable(slot(updated["summaries"], item_id, v)) for v in range(3))
                   for item_id in judgments)
    updated["n_complete"] = complete
    new_hash = sha256_lf(serialized(updated))
    updated_manifest = copy.deepcopy(manifest)
    updated_manifest["summaries"].update({
        "sha256_lf": new_hash, "represented_judgments": len(updated["summaries"]),
        "complete_judgments": complete, "usable_summaries": 2841 - len(remaining),
        "missing_slots_zero_based": remaining,
    })
    if sha256_lf(Path(cases_path).read_bytes()) != EXPECTED_DATA_SHA256:
        raise ValueError("Source dataset changed during generation; refusing publication")
    if (sha256_lf(Path(summaries_path).read_bytes()) != initial_summary_hash
            or sha256_lf(Path(manifest_path).read_bytes()) != initial_manifest_hash):
        raise ValueError("Summary artifact or manifest changed during generation; refusing overwrite")
    if new_hash not in checkpoint["published_artifact_hashes"]:
        checkpoint["published_artifact_hashes"].append(new_hash)
    checkpoint["remaining_missing_slots_zero_based"] = remaining
    checkpoint["repair_usage"] = {
        key: sum(attempt["usage"].get(key, 0) for attempt in checkpoint["attempts"])
        for key in ("prompt", "completion")
    }
    checkpoint["updated_utc"] = now()
    # Save the intended hash first so an interruption between artifact and manifest
    # writes can safely resume without another generation call.
    atomic_json(checkpoint_path, checkpoint)
    if successful:
        atomic_json(summaries_path, updated)
        atomic_json(manifest_path, updated_manifest)
    print(f"Summary coverage: {2841 - len(remaining)}/2,841; remaining: {len(remaining)}")
    return 1 if remaining else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=REPO / "data/processed/echr_unified.json")
    parser.add_argument("--summaries", type=Path, default=REPO / "data/processed/summaries_dsv41flash.json")
    parser.add_argument("--manifest", type=Path, default=REPO / "configs/evaluation_dataset.json")
    parser.add_argument("--checkpoint", type=Path,
                        default=REPO / "data/processed/summaries_dsv41flash.fill_checkpoint.json")
    parser.add_argument("--api-key-env", default="OPENROUTER_API_KEY")
    parser.add_argument("--workers", type=int, default=1, help="parallel missing slots, from 1 to 4")
    parser.add_argument("--execute", action="store_true", help="execute only the nine authorized missing slots")
    args = parser.parse_args(argv)
    try:
        return run(args.cases, args.summaries, args.manifest, args.checkpoint,
                   execute=args.execute, api_key_env=args.api_key_env, workers=args.workers)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Repair stopped: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
