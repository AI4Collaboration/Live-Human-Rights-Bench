"""Repair merges must preserve the source records and reject ambiguous inputs."""
import gzip
import json

import pytest

from quality_control.paraphrase.regen.merge_texts import merge_texts


def write_rows(path, rows):
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def read_rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


@pytest.fixture
def records(tmp_path):
    paths = [tmp_path / (name + ".jsonl.gz") for name in ("base", "regen", "merged", "subset")]
    rows = [
        {"item_id": "a", "article": "3", "condition": "original", "text": "Source facts."},
        {"item_id": "a", "article": "3", "condition": "low", "text": "Truncated."},
        {"item_id": "a", "article": "6", "condition": "original", "text": "Other target."},
        {"item_id": "b", "article": "3", "condition": "original", "text": "Other judgment."},
    ]
    write_rows(paths[0], rows)
    write_rows(paths[1], [dict(rows[1], text="Repaired facts.")])
    return paths, rows


def test_merge_preserves_order_and_includes_all_targets_of_affected_judgments(records):
    paths, rows = records
    before = [path.read_bytes() for path in paths[:2]]
    assert merge_texts(*paths) == (1, 1)
    expected = [rows[0], dict(rows[1], text="Repaired facts."), *rows[2:]]
    assert read_rows(paths[2]) == expected
    assert read_rows(paths[3]) == expected[:3]
    assert [path.read_bytes() for path in paths[:2]] == before


@pytest.mark.parametrize("problem", ["original", "duplicate_regen", "duplicate_base", "unknown"])
def test_invalid_repair_creates_no_outputs(records, problem):
    paths, rows = records
    if problem == "original":
        write_rows(paths[1], [dict(rows[0], text="Changed source facts.")])
    elif problem == "duplicate_regen":
        write_rows(paths[1], [rows[1], rows[1]])
    elif problem == "duplicate_base":
        write_rows(paths[0], [*rows, rows[0]])
    else:
        write_rows(paths[1], [dict(rows[1], item_id="missing")])
    before = [path.read_bytes() for path in paths[:2]]
    with pytest.raises(ValueError):
        merge_texts(*paths)
    assert not paths[2].exists() and not paths[3].exists()
    assert [path.read_bytes() for path in paths[:2]] == before


@pytest.mark.parametrize("output_index", [2, 3])
def test_existing_outputs_are_not_overwritten(records, output_index):
    paths, _ = records
    paths[output_index].write_bytes(b"Existing artifact")
    with pytest.raises(FileExistsError):
        merge_texts(*paths)
    assert paths[output_index].read_bytes() == b"Existing artifact"
    assert not paths[5 - output_index].exists()


@pytest.mark.parametrize("first,second", [(0, 2), (1, 2), (0, 3), (1, 3), (2, 3)])
def test_paths_cannot_alias_inputs_or_each_other(records, first, second):
    paths, _ = records
    before = [path.read_bytes() for path in paths[:2]]
    paths[second] = paths[first]
    with pytest.raises(ValueError, match="distinct"):
        merge_texts(*paths)
    assert [path.read_bytes() for path in paths[:2]] == before
