"""Static integration checks only. These do not execute VBA or emulate Excel."""

import importlib.util
import re
from pathlib import Path

from openpyxl import load_workbook

from doctree.generator import generate
from doctree.reporting import build_report

ROOT = Path(__file__).parents[1]


def test_exported_module_and_workbook_table_contracts(config):
    source = (ROOT / "vba/DocTreeQA.bas").read_text(encoding="ascii")
    assert source.startswith('Attribute VB_Name = "DocTreeQA"\nOption Explicit')
    assert set(re.findall(r"Public Sub (\w+)\(", source)) == {
        "HighlightIssues",
        "BuildSystemSummary",
        "MarkReviewed",
    }
    generate(config)
    build_report(config)
    wb = load_workbook(config.reports_dir / "doctree_report.xlsx")
    # Verify the actual VBA schema references against an exported workbook, so Python
    # column/table renames cannot silently break the reviewer macros.
    collapsed = re.sub(r"_\s*\n\s*", " ", source)
    procedures = re.findall(r"Public Sub .*?End Sub", collapsed, flags=re.DOTALL)
    for procedure in procedures:
        assignments = dict(
            (variable, (sheet, table))
            for variable, sheet, table in re.findall(
                r'Set (\w+) = GetTable\("([^"]+)", "([^"]+)"\)', procedure
            )
        )
        for variable, arguments in re.findall(r"RequireColumns (\w+), Array\((.*?)\)", procedure):
            sheet, table_name = assignments[variable]
            table = wb[sheet].tables[table_name]
            actual_headers = {column.name for column in table.tableColumns}
            assert set(re.findall(r'"([^"]+)"', arguments)) <= actual_headers
    wb.close()


def test_reference_counts_preserve_unmapped_findings_and_review_semantics(config):
    generate(config)
    build_report(config)
    spec = importlib.util.spec_from_file_location(
        "reference", ROOT / "scripts/prepare_excel_acceptance.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    reference = module.prepare(config.root)
    assert reference["initial_open_findings"] == 200
    assert reference["initial_unmapped_open"] == 16
    assert reference["after_accepting_first_row"] == 200
    assert reference["after_rejecting_same_first_row"] == 199
    assert "Not run" in reference["vba_runtime_status"]
