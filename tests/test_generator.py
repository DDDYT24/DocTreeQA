import hashlib
from dataclasses import replace

import pytest

from doctree.generator import generate
from doctree.io import DOC_FIELDS, TRUTH_FIELDS, read_csv


def hashes(directory):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.iterdir()}


def test_generation_is_byte_identical(config):
    generate(config)
    first = hashes(config.data_dir)
    generate(config, force=True)
    assert hashes(config.data_dir) == first


def test_refuse_accidental_overwrite(config):
    generate(config)
    before = hashes(config.data_dir)
    with pytest.raises(ValueError, match="--force"):
        generate(config)
    assert hashes(config.data_dir) == before


def test_document_identity_is_independent_of_doc_id(config):
    manifest = generate(config)
    rows = read_csv(config.data_dir / "document_register.csv", DOC_FIELDS)
    assert len(rows) == manifest["document_count"]
    assert len({r["row_id"] for r in rows}) == len(rows)
    assert len({r["doc_id"] for r in rows}) < len(rows)


def test_faults_are_logged_including_cascades(config):
    generate(config)
    truth = read_csv(config.data_dir / "injected_errors.csv", TRUTH_FIELDS)
    assert {row["error_type"] for row in truth} >= {
        "missing_revision",
        "missing_title",
        "unknown_equipment",
        "duplicate_doc_id",
        "duplicate_file",
        "filename_mismatch",
        "orphan_superseded",
        "future_date",
        "wrong_mapping_level",
        "missing_required",
    }
    file_events = [r for r in truth if r["error_type"] == "duplicate_file"]
    assert {r["rule"] for r in file_events} == {
        "duplicate_file",
        "filename_mismatch",
        "near_duplicate_title",
    }


def test_clean_generation_and_small_dataset(config):
    small = replace(config, systems=1, subsystems=2, equipment=5, documents=50, errors_per_type=0)
    manifest = generate(small)
    assert manifest["injection_events"] == 0
    assert manifest["document_count"] == 50


def test_not_enough_equipment_rejected_before_write(config):
    with pytest.raises(ValueError, match="isolated"):
        generate(replace(config, equipment=50, documents=500))
    assert not config.data_dir.exists()
