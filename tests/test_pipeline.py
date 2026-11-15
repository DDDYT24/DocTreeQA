import csv
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from doctree.cli import main
from doctree.generator import generate
from doctree.io import DOC_FIELDS, REQUIRED_FIELDS, TREE_FIELDS, read_csv, write_csv
from doctree.pipeline import check


def test_full_benchmark_scores_all_injected_findings(config):
    manifest = generate(config)
    before = hashlib.sha256((config.data_dir / "document_register.csv").read_bytes()).hexdigest()
    summary = check(config)
    after = hashlib.sha256((config.data_dir / "document_register.csv").read_bytes()).hexdigest()
    scores = json.loads((config.reports_dir / "scoring.json").read_text())
    assert before == after
    assert summary["document_count"] == manifest["document_count"]
    assert scores["overall"]["support"] == manifest["expected_findings"]
    assert scores["overall"]["precision"] == 1
    assert scores["overall"]["recall"] == 1
    assert scores["false_positives"] == []
    assert scores["false_negatives"] == []
    assert scores["per_rule"]["tree_cycle"]["recall"] is None
    assert summary["completeness"]["missing_count"] == config.errors_per_type
    assert summary["completeness"]["trustworthy_tree"] is True


@pytest.mark.parametrize("seed", [0, 29, 104729])
def test_scoring_is_consistent_across_seeds(config, seed):
    generate(replace(config, seed=seed))
    check(config)
    scoring = json.loads((config.reports_dir / "scoring.json").read_text())
    assert not scoring["false_positives"]
    assert not scoring["false_negatives"]


def test_detectors_do_not_require_or_use_answer_key(config):
    generate(config)
    check(config)
    issues_before = (config.reports_dir / "issues.csv").read_bytes()
    (config.data_dir / "injected_errors.csv").unlink()
    summary = check(config)
    assert (config.reports_dir / "issues.csv").read_bytes() == issues_before
    assert summary["scoring_available"] is False
    assert not (config.reports_dir / "scoring.json").exists()


def test_clean_benchmark_produces_no_findings(config):
    generate(replace(config, errors_per_type=0))
    summary = check(config)
    assert summary["issue_count"] == 0
    assert summary["change_count"] == 0
    assert summary["completeness"]["completeness_pct"] == 100


def test_csv_headers_row_counts_and_json_match(config):
    generate(config)
    summary = check(config)
    assert json.loads((config.reports_dir / "summary.json").read_text()) == summary
    for name, count, headers in [
        ("issues.csv", summary["issue_count"], {"severity", "rule", "entity_id", "system_code"}),
        (
            "manual_review.csv",
            summary["manual_review_count"],
            {"review_id", "decision", "initials", "reviewed_at"},
        ),
        ("change_log.csv", summary["change_count"], {"before", "after", "row_id", "field"}),
        ("completeness.csv", summary["node_count"], {"required_count", "completeness_pct"}),
        ("document_register_cleaned.csv", summary["document_count"], set(DOC_FIELDS)),
    ]:
        with (config.reports_dir / name).open(newline="") as stream:
            reader = csv.DictReader(stream)
            assert set(reader.fieldnames) >= headers
            assert len(list(reader)) == count
    assert summary["runtime_seconds"] > 0
    assert set(summary["input_sha256"]) == {
        "equipment_tree.csv",
        "document_register.csv",
        "required_docs.csv",
        "injected_errors.csv",
    }


def test_optional_row_ids_derived_from_source_order(config, sample):
    tree, docs, required = sample
    for row in docs:
        row.pop("row_id")
    write_csv(config.data_dir / "equipment_tree.csv", TREE_FIELDS, tree)
    write_csv(
        config.data_dir / "document_register.csv", [f for f in DOC_FIELDS if f != "row_id"], docs
    )
    write_csv(config.data_dir / "required_docs.csv", REQUIRED_FIELDS, required)
    summary = check(config)
    assert summary["row_ids_from_source"] is False
    cleaned = read_csv(config.reports_dir / "document_register_cleaned.csv", DOC_FIELDS)
    assert cleaned[0]["row_id"] == "ROW-000001"


def test_cli_run_and_fail_on_issues_exit_codes(config, capsys):
    # Use the real project configuration shape with temporary absolute output paths.
    raw = yaml.safe_load((Path(__file__).parents[1] / "configs/default.yaml").read_text())
    raw["paths"] = dict(data_dir=str(config.data_dir), reports_dir=str(config.reports_dir))
    path = config.root / "temporary.yaml"
    path.write_text(yaml.safe_dump(raw))
    assert main(["--config", str(path), "generate"]) == 0
    assert main(["--config", str(path), "check"]) == 0
    assert main(["--config", str(path), "check", "--fail-on-issues"]) == 1
    assert main(["--config", str(path), "generate"]) == 2
    assert "--force" in capsys.readouterr().err


def test_missing_inputs_return_useful_cli_error(tmp_path, capsys):
    assert main(["--config", str(tmp_path / "absent.yaml"), "check"]) == 2
    assert "doctree:" in capsys.readouterr().err


def test_report_cli_exports_workbook(config):
    raw = yaml.safe_load((Path(__file__).parents[1] / "configs/default.yaml").read_text())
    raw["paths"] = dict(data_dir=str(config.data_dir), reports_dir=str(config.reports_dir))
    path = config.root / "temporary.yaml"
    path.write_text(yaml.safe_dump(raw))
    generate(config)
    assert main(["--config", str(path), "report"]) == 0
    assert (config.reports_dir / "doctree_report.xlsx").exists()
    assert main(["--config", str(path), "report"]) == 2
    assert main(["--config", str(path), "report", "--force"]) == 0
