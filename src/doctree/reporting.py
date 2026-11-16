"""Create a macro-free review workbook from a fresh validation run."""

import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path
from tempfile import NamedTemporaryFile

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.formatting.rule import DataBarRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter, range_boundaries
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.pagebreak import Break
from openpyxl.worksheet.table import Table, TableStyleInfo

from doctree.config import Config
from doctree.fixes import CHANGE_FIELDS
from doctree.io import read_csv, write_json
from doctree.pipeline import COMPLETENESS_FIELDS, ISSUE_FIELDS, check

HEADER_ROW = 5
SHEET_NAMES = ["Summary", "Issues", "Completeness", "Manual Review", "Change Log"]
MANUAL_FIELDS = [
    "review_id",
    "decision",
    "initials",
    "reviewed_at",
    *ISSUE_FIELDS,
]
NAVY, TEAL, WHITE = "18354A", "176B75", "FFFFFF"
SEVERITY_COLORS = {"error": "FCE4D6", "warning": "FFF2CC", "info": "DDEBF7"}


def _value(cell, value):
    if isinstance(value, str):
        if ILLEGAL_CHARACTERS_RE.search(value) or len(value) > 32767:
            raise ValueError("Excel cell contains a control character or exceeds its text limit")
        cell.value = value
        # Preserve source text, including leading '=' and numeric-looking identifiers.
        cell.data_type = "s"
        cell.number_format = "@"
    else:
        cell.value = value


def _banner(ws, title, note, columns):
    end = max(columns, 5)
    for row in (1, 2, 3):
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=end)
    _value(ws.cell(1, 1), title)
    _value(ws.cell(2, 1), "SYNTHETIC DATA ONLY | Fictional metadata; no real ship or Seaspan data")
    _value(ws.cell(3, 1), note)
    ws.cell(1, 1).font = Font(name="Calibri", size=20, bold=True, color=WHITE)
    ws.cell(1, 1).fill = PatternFill("solid", fgColor=NAVY)
    ws.cell(2, 1).font = Font(name="Calibri", size=11, bold=True, color=TEAL)
    ws.cell(3, 1).font = Font(name="Calibri", size=10, color="485C68")
    for row in (1, 2, 3):
        ws.cell(row, 1).alignment = Alignment(vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 36
    ws.row_dimensions[2].height = 24
    ws.row_dimensions[3].height = 32
    ws.sheet_view.showGridLines = False
    ws.sheet_view.zoomScale = 85
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A3
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.print_title_rows = "1:5"
    ws.oddFooter.center.text = "SYNTHETIC | DocTreeQA | Page &P of &N"
    ws.sheet_properties.tabColor = TEAL


def _table(ws, name, headers, rows, *, start_row=HEADER_ROW):
    for column, header in enumerate(headers, start=1):
        cell = ws.cell(start_row, column)
        _value(cell, header)
        cell.font = Font(name="Calibri", size=11, bold=True, color=WHITE)
        cell.fill = PatternFill("solid", fgColor=NAVY)
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    ws.row_dimensions[start_row].height = 28
    for row_index, record in enumerate(rows, start=start_row + 1):
        for column, header in enumerate(headers, start=1):
            cell = ws.cell(row_index, column)
            _value(cell, record[header])
            cell.font = Font(name="Calibri", size=11, color=NAVY)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
        ws.row_dimensions[row_index].height = 32
    ref = f"A{start_row}:{get_column_letter(len(headers))}{start_row + len(rows)}"
    table = Table(displayName=name, ref=ref)
    table.tableStyleInfo = TableStyleInfo(
        name="TableStyleMedium2",
        showFirstColumn=False,
        showLastColumn=False,
        showRowStripes=True,
        showColumnStripes=False,
    )
    ws.add_table(table)
    return table


def _widths(ws, headers):
    widths = {
        "severity": 12,
        "rule": 36,
        "doc_id": 22,
        "equipment_code": 20,
        "message": 64,
        "suggested_action": 68,
        "entity_type": 16,
        "entity_id": 35,
        "row_id": 20,
        "system_code": 16,
        "subsystem_code": 20,
        "review_status": 18,
        "review_id": 20,
        "decision": 16,
        "initials": 14,
        "reviewed_at": 24,
        "code": 22,
        "parent_code": 22,
        "level": 18,
        "name": 54,
        "equipment_class": 22,
        "required_count": 20,
        "present_count": 20,
        "missing_count": 20,
        "completeness_pct": 22,
        "missing_types": 38,
        "field": 28,
        "before": 66,
        "after": 66,
        "reason": 66,
    }
    for index, header in enumerate(headers, start=1):
        ws.column_dimensions[get_column_letter(index)].width = widths.get(header, 22)


def _hierarchy(rows):
    by_code = {r["code"]: r for r in rows}
    children = defaultdict(list)
    for row in rows:
        children[row["parent_code"]].append(row["code"])
    roots = [r["code"] for r in rows if r["parent_code"] not in by_code]
    visited, ordered = set(), []
    # Remaining nodes cover malformed cycles too, without dropping data or hanging.
    for root in [*roots, *by_code]:
        stack = [(root, 0)]
        while stack:
            code, depth = stack.pop()
            if code in visited:
                continue
            visited.add(code)
            record = dict(by_code[code])
            for field in ("required_count", "present_count", "missing_count"):
                record[field] = int(record[field])
            record["completeness_pct"] = (
                float(record["completeness_pct"]) / 100 if record["completeness_pct"] else None
            )
            ordered.append((record, depth))
            stack.extend((child, depth + 1) for child in reversed(children[code]))
    return ordered


def _summary(ws, summary, scoring):
    _banner(
        ws,
        "DocTreeQA | Documentation QA",
        (
            f"Review date: {summary['as_of_date']} | Generated snapshot. "
            "Reviewer decisions stay in the workbook; rebuild the VBA System Summary after review."
        ),
        5,
    )
    coverage = summary["completeness"]
    ws.print_title_rows = "1:3"
    metrics = [
        (
            "Document register rows",
            summary["document_count"],
            "Metadata records, including revisions",
        ),
        ("Equipment items", summary["equipment_count"], "Equipment level nodes"),
        ("Systems", summary["system_count"], "Top level nodes"),
        ("Subsystems", summary["subsystem_count"], "Intermediate nodes"),
        ("Open findings at generation", summary["issue_count"], "Human decisions required"),
        (
            "Error findings",
            summary["issues_per_severity"].get("error", 0),
            "Investigate and correct",
        ),
        ("Warning findings", summary["issues_per_severity"].get("warning", 0), "Review candidates"),
        (
            "Safe changes at generation",
            summary["change_count"],
            "Whitespace and doc_type casing only",
        ),
        (
            "Required document types",
            coverage["required_count"],
            "Sum across equipment requirements",
        ),
        ("Present required types", coverage["present_count"], "Mapped issued metadata records"),
        (
            "Missing required types",
            coverage["missing_count"],
            "Required types without an issued record",
        ),
        (
            "Completeness",
            coverage["completeness_pct"] / 100
            if coverage["completeness_pct"] is not None
            else None,
            "Percent; inventory coverage, not acceptance",
        ),
        (
            "Tree rollups trustworthy",
            coverage["trustworthy_tree"],
            "False: repair tree or classes first",
        ),
        (
            "Check runtime, seconds",
            summary["runtime_seconds"],
            "Input load, checks, CSV export and scoring",
        ),
        ("Review date", summary["as_of_date"], "Fixed date used for future-date checks"),
        ("Seed", summary["seed"], "Synthetic generation seed"),
    ]
    _table(
        ws,
        "SummaryMetrics",
        ["metric", "value", "meaning"],
        [dict(metric=name, value=value, meaning=meaning) for name, value, meaning in metrics],
    )
    for index, (name, _, _) in enumerate(metrics, start=HEADER_ROW + 1):
        ws.row_dimensions[index].height = 26
        ws.cell(index, 2).alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(index, 3).alignment = Alignment(indent=1, vertical="center", wrap_text=True)
        if name == "Completeness":
            ws.cell(index, 2).number_format = "0.00%"
    start = HEADER_ROW + len(metrics) + 4
    score_rows = []
    if scoring:
        for rule, values in scoring["per_rule"].items():
            score_rows.append(
                dict(
                    rule=rule,
                    findings=summary["issues_per_rule"].get(rule, 0),
                    expected=values["support"],
                    precision=values["precision"],
                    recall=values["recall"],
                )
            )
    else:
        score_rows = [
            dict(rule=rule, findings=count, expected=None, precision=None, recall=None)
            for rule, count in summary["issues_per_rule"].items()
        ]
    _value(ws.cell(start - 1, 1), "Per-rule findings and controlled synthetic scoring")
    ws.cell(start - 1, 1).font = Font(bold=True, color=TEAL, size=12)
    _table(
        ws,
        "RuleMetrics",
        ["rule", "findings", "expected", "precision", "recall"],
        score_rows,
        start_row=start,
    )
    ws.row_breaks.append(Break(id=start - 2))
    for row in range(start + 1, start + len(score_rows) + 1):
        ws.row_dimensions[row].height = 20
        for column in (4, 5):
            ws.cell(row, column).number_format = "0.00%"
    notes = [
        "Blank precision or recall means no denominator, not perfect performance.",
        "safe_normalization is scored from Change Log; it is not an open Issue.",
        "Accepted = finding retained as Open. Rejected = finding Dismissed. "
        "Neither changes source data.",
        "Shared file names and title similarity are candidates for manual review, "
        "not proof of content.",
        "Use the VBA module from vba/DocTreeQA.bas in a separately saved .xlsm review copy.",
        "For Windows Excel runtime evidence, see docs/windows_acceptance.md.",
    ]
    note_start = start + len(score_rows) + 3
    for index, note in enumerate(notes, start=note_start):
        ws.merge_cells(start_row=index, start_column=1, end_row=index, end_column=5)
        _value(ws.cell(index, 1), note)
        ws.cell(index, 1).alignment = Alignment(wrap_text=True, vertical="center")
        ws.cell(index, 1).font = Font(name="Calibri", size=10, color="485C68")
        ws.row_dimensions[index].height = 28
    for column, width in {"A": 39, "B": 22, "C": 58, "D": 18, "E": 18}.items():
        ws.column_dimensions[column].width = width
    ws.freeze_panes = "B6"
    ws.print_area = f"A1:E{note_start + len(notes) - 1}"


def build_report(config: Config, *, force: bool = False) -> dict:
    target = config.reports_dir / "doctree_report.xlsx"
    if target.exists() and not force:
        raise ValueError(
            "Workbook already exists; keep review copies separately or use report --force"
        )
    summary = check(config)
    output = config.reports_dir
    issues = read_csv(output / "issues.csv", ISSUE_FIELDS)
    manual = read_csv(output / "manual_review.csv", MANUAL_FIELDS)
    changes = read_csv(output / "change_log.csv", CHANGE_FIELDS)
    hierarchy = _hierarchy(read_csv(output / "completeness.csv", COMPLETENESS_FIELDS))
    scoring = (
        json.loads((output / "scoring.json").read_text()) if summary["scoring_available"] else None
    )
    wb = Workbook()
    wb.remove(wb.active)
    for name in SHEET_NAMES:
        wb.create_sheet(name)
    wb.properties.creator = "DocTreeQA"
    wb.properties.title = "Synthetic technical document QA"
    wb.properties.description = "Fictional generated metadata. No real ship or company data."
    _summary(wb["Summary"], summary, scoring)
    definitions = [
        (
            "Issues",
            "IssuesTable",
            ISSUE_FIELDS,
            issues,
            "Generated findings. Use MarkReviewed on Manual Review to retain or dismiss a finding.",
            "E6",
        ),
        (
            "Completeness",
            "CompletenessTable",
            COMPLETENESS_FIELDS,
            [r for r, _ in hierarchy],
            "Issued type coverage only. Blank percentage = no denominator. "
            f"Tree trustworthy: {summary['completeness']['trustworthy_tree']}.",
            "D6",
        ),
        (
            "Manual Review",
            "ManualReviewTable",
            MANUAL_FIELDS,
            manual,
            "Use MarkReviewed: Accepted keeps a finding Open; Rejected dismisses it. "
            "Initials and time use your local Excel session.",
            "E6",
        ),
        (
            "Change Log",
            "ChangeLogTable",
            CHANGE_FIELDS,
            changes,
            "Generated safe changes are applied to the cleaned CSV only. "
            "MarkReviewed appends workbook review changes to this log.",
            "D6",
        ),
    ]
    for name, table_name, headers, records, note, freeze in definitions:
        ws = wb[name]
        _banner(ws, f"DocTreeQA | {name}", note, len(headers))
        _table(ws, table_name, headers, records)
        _widths(ws, headers)
        ws.freeze_panes = freeze
        ws.print_area = f"A1:{get_column_letter(len(headers))}{HEADER_ROW + len(records)}"
        if name == "Issues":
            for index, record in enumerate(records, start=HEADER_ROW + 1):
                color = SEVERITY_COLORS.get(record["severity"], WHITE)
                for cell in ws[index][: len(headers)]:
                    cell.fill = PatternFill("solid", fgColor=color)
                ws.row_dimensions[index].height = 44
        if name == "Manual Review":
            for index in range(HEADER_ROW + 1, HEADER_ROW + len(records) + 1):
                for column in (2, 3, 4):
                    ws.cell(index, column).fill = PatternFill("solid", fgColor="FFF7DE")
            if records:
                for field, formula in (
                    ("decision", '"Pending,Accepted,Rejected"'),
                    ("review_status", '"Open,Dismissed"'),
                ):
                    validation = DataValidation(type="list", formula1=formula, allow_blank=False)
                    validation.errorTitle = "Choose a listed value"
                    validation.error = "Use MarkReviewed to synchronize the finding and audit log."
                    validation.showErrorMessage = True
                    validation.errorStyle = "stop"
                    ws.add_data_validation(validation)
                    column = get_column_letter(headers.index(field) + 1)
                    validation.add(f"{column}6:{column}{HEADER_ROW + len(records)}")
        if name == "Completeness":
            ws.sheet_properties.outlinePr.summaryRight = False
            ws.sheet_properties.outlinePr.summaryBelow = False
            for index, (record, depth) in enumerate(hierarchy, start=HEADER_ROW + 1):
                ws.row_dimensions[index].outlineLevel = min(depth, 7)
                ws.cell(index, 4).alignment = Alignment(indent=min(depth, 15), vertical="center")
                percent_column = headers.index("completeness_pct") + 1
                ws.cell(index, percent_column).number_format = "0.00%"
                if record["level"] in {"System", "Subsystem"}:
                    for cell in ws[index][: len(headers)]:
                        cell.font = Font(name="Calibri", bold=True, color=NAVY)
                        cell.fill = PatternFill(
                            "solid", fgColor=("DCECF1" if record["level"] == "System" else "EDF3F5")
                        )
                if record["missing_count"]:
                    ws.cell(index, headers.index("missing_count") + 1).font = Font(
                        color="A82020", bold=True
                    )
            if hierarchy:
                column = get_column_letter(COMPLETENESS_FIELDS.index("completeness_pct") + 1)
                ws.conditional_formatting.add(
                    f"{column}6:{column}{HEADER_ROW + len(hierarchy)}",
                    DataBarRule(
                        start_type="num",
                        start_value=0,
                        end_type="num",
                        end_value=1,
                        color="5FACA0",
                        showValue=True,
                    ),
                )
    with NamedTemporaryFile(dir=output, suffix=".xlsx", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        wb.save(temporary)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
        wb.close()
    sources = [
        "summary.json",
        "issues.csv",
        "manual_review.csv",
        "completeness.csv",
        "change_log.csv",
    ]
    if summary["scoring_available"]:
        sources.append("scoring.json")
    manifest = dict(
        synthetic=True,
        workbook=target.name,
        workbook_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
        header_row=HEADER_ROW,
        data_rows={
            "Summary": None,
            "Issues": len(issues),
            "Completeness": len(hierarchy),
            "Manual Review": len(manual),
            "Change Log": len(changes),
        },
        table_rows={
            table.displayName: range_boundaries(table.ref)[3] - range_boundaries(table.ref)[1]
            for sheet in wb
            for table in sheet.tables.values()
        },
        source_sha256={
            name: hashlib.sha256((output / name).read_bytes()).hexdigest() for name in sources
        },
        vba_included=False,
        vba_execution_status=(
            "Macro-free workbook; review-copy runtime evidence is recorded separately"
        ),
        review_semantics={"Accepted": "Open", "Rejected": "Dismissed"},
    )
    write_json(output / "workbook_manifest.json", manifest)
    return manifest
