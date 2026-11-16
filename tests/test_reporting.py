import csv
import hashlib
import json
import zipfile
from dataclasses import replace

import pytest
from openpyxl import load_workbook

from doctree.generator import generate
from doctree.io import DOC_FIELDS, REQUIRED_FIELDS, TREE_FIELDS, read_csv, write_csv
from doctree.reporting import HEADER_ROW, SHEET_NAMES, build_report


def records(ws, table_name):
    table = ws.tables[table_name]
    rows = list(ws[table.ref])
    headers = [cell.value for cell in rows[0]]
    return [dict(zip(headers, [cell.value for cell in row], strict=True)) for row in rows[1:]]


def test_workbook_sheets_tables_counts_and_source_values(config):
    generate(config)
    manifest = build_report(config)
    path = config.reports_dir / "doctree_report.xlsx"
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        assert not any(
            "vbaProject" in name or "externalLinks" in name for name in archive.namelist()
        )
    wb = load_workbook(path)
    assert wb.sheetnames == SHEET_NAMES
    for sheet, table in [
        ("Issues", "IssuesTable"),
        ("Manual Review", "ManualReviewTable"),
        ("Change Log", "ChangeLogTable"),
    ]:
        actual = records(wb[sheet], table)
        filename = {
            "Issues": "issues.csv",
            "Manual Review": "manual_review.csv",
            "Change Log": "change_log.csv",
        }[sheet]
        with (config.reports_dir / filename).open(newline="") as stream:
            expected = list(csv.DictReader(stream))
        assert len(actual) == len(expected) == manifest["data_rows"][sheet]
        # Empty Excel text cells round-trip as None, rather than an empty string.
        assert [{k: value or "" for k, value in row.items()} for row in actual] == expected
        assert wb[sheet].tables[table].autoFilter.ref == wb[sheet].tables[table].ref
    for ws in wb:
        assert "SYNTHETIC" in ws["A2"].value
        assert ws.freeze_panes
        assert ws["A1"].font.color.rgb == "00000000"
        assert ws["A1"].fill.fgColor.rgb == "00FFFFFF"
        assert ws["A5"].font.color.rgb == "00000000"
        assert ws["A5"].border.bottom.style == "thin"
        assert ws["A5"].border.bottom.color.rgb == "00000000"
        for table in ws.tables.values():
            assert table.tableStyleInfo.name == "TableStyleLight1"
            assert table.tableStyleInfo.showRowStripes is False
            assert manifest["table_rows"][table.displayName] == len(list(ws[table.ref])) - 1
    saved = json.loads((config.reports_dir / "summary.json").read_text())
    metrics = {r["metric"]: r["value"] for r in records(wb["Summary"], "SummaryMetrics")}
    assert metrics["Document register rows"] == saved["document_count"]
    assert metrics["Open findings at generation"] == saved["issue_count"]
    assert metrics["Tree rollups trustworthy"] is True
    assert metrics["Check runtime, seconds"] == saved["runtime_seconds"]
    assert metrics["Completeness"] == pytest.approx(saved["completeness"]["completeness_pct"] / 100)
    for name, digest in manifest["source_sha256"].items():
        assert hashlib.sha256((config.reports_dir / name).read_bytes()).hexdigest() == digest
    assert manifest["workbook_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    wb.close()


def test_completeness_is_a_numeric_tree_view(config):
    generate(config)
    manifest = build_report(config)
    wb = load_workbook(config.reports_dir / "doctree_report.xlsx")
    ws = wb["Completeness"]
    rows = records(ws, "CompletenessTable")
    assert len(rows) == manifest["data_rows"]["Completeness"]
    assert rows[0]["level"] == "System"
    assert rows[1]["level"] == "Subsystem"
    assert rows[2]["level"] == "Equipment"
    positions = {r["code"]: index for index, r in enumerate(rows)}
    csv_rows = {
        r["code"]: r for r in read_csv(config.reports_dir / "completeness.csv", TREE_FIELDS)
    }
    for index, row in enumerate(rows, start=HEADER_ROW + 1):
        if row["parent_code"]:
            assert positions[row["parent_code"]] < positions[row["code"]]
        assert 0 <= row["completeness_pct"] <= 1
        assert row["completeness_pct"] == pytest.approx(
            float(csv_rows[row["code"]]["completeness_pct"]) / 100
        )
        assert isinstance(row["required_count"], int)
        assert (
            ws.row_dimensions[index].outlineLevel
            == {"System": 0, "Subsystem": 1, "Equipment": 2}[row["level"]]
        )
    assert len(ws.conditional_formatting) == 1
    wb.close()


def test_reviewer_fields_validation_and_severity_colours(config):
    generate(config)
    build_report(config)
    wb = load_workbook(config.reports_dir / "doctree_report.xlsx")
    ws = wb["Manual Review"]
    assert [ws.cell(HEADER_ROW, i).value for i in range(1, 5)] == [
        "review_id",
        "decision",
        "initials",
        "reviewed_at",
    ]
    assert any(
        rule.formula1 == '"Pending,Accepted,Rejected"'
        for rule in ws.data_validations.dataValidation
    )
    issue_rows = records(wb["Issues"], "IssuesTable")
    for index, row in enumerate(issue_rows, start=HEADER_ROW + 1):
        expected = "FCE4D6" if row["severity"] == "error" else "FFF2CC"
        assert wb["Issues"].cell(index, 1).fill.fgColor.rgb == "00" + expected
    wb.close()


def test_report_refuses_to_replace_existing_review_workbook(config):
    generate(config)
    build_report(config)
    path = config.reports_dir / "doctree_report.xlsx"
    path.write_bytes(b"stand-in for a workbook containing reviewer edits")
    summary_before = (config.reports_dir / "summary.json").read_bytes()
    with pytest.raises(ValueError, match="--force"):
        build_report(config)
    assert path.read_bytes() == b"stand-in for a workbook containing reviewer edits"
    assert (config.reports_dir / "summary.json").read_bytes() == summary_before


def test_report_reruns_checks_instead_of_using_stale_csv(config):
    generate(config)
    first = build_report(config)
    docs_path = config.data_dir / "document_register.csv"
    docs = read_csv(docs_path, DOC_FIELDS)
    docs[0]["title"] = ""
    write_csv(docs_path, DOC_FIELDS, docs)
    second = build_report(config, force=True)
    assert second["data_rows"]["Issues"] == first["data_rows"]["Issues"] + 1


def test_empty_findings_have_headers_without_fake_records(config):
    generate(replace(config, errors_per_type=0))
    manifest = build_report(config)
    wb = load_workbook(config.reports_dir / "doctree_report.xlsx")
    assert manifest["data_rows"]["Issues"] == 0
    assert records(wb["Issues"], "IssuesTable") == []
    assert records(wb["Manual Review"], "ManualReviewTable") == []
    assert records(wb["Change Log"], "ChangeLogTable") == []
    wb.close()


@pytest.mark.parametrize("text", ["=1+1", "+SUM(A1)", "@SUM(A1)", "000123"])
def test_source_text_is_never_exported_as_a_formula(config, sample, text):
    tree, docs, required = sample
    docs[1]["title"] = " " + text + " "
    write_csv(config.data_dir / "equipment_tree.csv", TREE_FIELDS, tree)
    write_csv(config.data_dir / "document_register.csv", DOC_FIELDS, docs)
    write_csv(config.data_dir / "required_docs.csv", REQUIRED_FIELDS, required)
    build_report(config)
    wb = load_workbook(config.reports_dir / "doctree_report.xlsx", data_only=False)
    ws = wb["Change Log"]
    assert ws["D6"].value == " " + text + " "
    assert ws["E6"].value == text
    assert ws["E6"].data_type == "s"
    for sheet in wb:
        assert not any(cell.data_type == "f" for row in sheet for cell in row)
    wb.close()


def test_cyclic_tree_is_exported_and_marked_untrustworthy(config, sample):
    tree, docs, required = sample
    tree[0]["parent_code"] = "P-1"
    write_csv(config.data_dir / "equipment_tree.csv", TREE_FIELDS, tree)
    write_csv(config.data_dir / "document_register.csv", DOC_FIELDS, docs)
    write_csv(config.data_dir / "required_docs.csv", REQUIRED_FIELDS, required)
    manifest = build_report(config)
    assert manifest["data_rows"]["Completeness"] == len(tree)
    wb = load_workbook(config.reports_dir / "doctree_report.xlsx")
    metrics = {r["metric"]: r["value"] for r in records(wb["Summary"], "SummaryMetrics")}
    assert metrics["Tree rollups trustworthy"] is False
    assert "False" in wb["Completeness"]["A3"].value
    wb.close()


@pytest.mark.parametrize("title", ["bad\x01text", "a" * 32768])
def test_excel_unrepresentable_text_is_rejected_without_truncation(config, sample, title):
    tree, docs, required = sample
    docs[1]["title"] = " " + title + " "
    write_csv(config.data_dir / "equipment_tree.csv", TREE_FIELDS, tree)
    write_csv(config.data_dir / "document_register.csv", DOC_FIELDS, docs)
    write_csv(config.data_dir / "required_docs.csv", REQUIRED_FIELDS, required)
    with pytest.raises(ValueError, match="control character|text limit"):
        build_report(config)
    assert not (config.reports_dir / "doctree_report.xlsx").exists()
