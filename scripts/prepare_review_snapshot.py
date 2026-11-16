"""Create presentation copies of an inspected review workbook without running macros."""

import argparse
import hashlib
import json
import zipfile
from copy import copy
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.packaging.core import DocumentProperties
from openpyxl.packaging.custom import CustomPropertyList
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import range_boundaries
from openpyxl.worksheet.table import TableStyleInfo

from doctree.io import read_csv
from doctree.reporting import BLACK, LIGHT_GRAY, SEVERITY_COLORS, TABLE_BORDER, WHITE

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def macro_digest(path):
    with zipfile.ZipFile(path) as archive:
        return hashlib.sha256(archive.read("xl/vbaProject.bin")).hexdigest()


def restyle(workbook, names):
    renamed = []
    for ws in workbook:
        ws.sheet_properties.tabColor = BLACK
        ws.sheet_view.showGridLines = False
        for row in ws:
            for cell in row:
                font = copy(cell.font)
                font.name, font.color = "Calibri", BLACK
                cell.font = font
                cell.fill = PatternFill("solid", fgColor=WHITE)
        for cell in ws[1]:
            cell.border = TABLE_BORDER
        for table in ws.tables.values():
            table.tableStyleInfo = TableStyleInfo(name="TableStyleLight1", showRowStripes=False)
            left, top, right, bottom = range_boundaries(table.ref)
            headers = {ws.cell(top, c).value: c for c in range(left, right + 1)}
            for row in ws.iter_rows(min_row=top, max_row=bottom, min_col=left, max_col=right):
                for cell in row:
                    cell.border = TABLE_BORDER
                    if cell.row == top:
                        cell.fill = PatternFill("solid", fgColor=LIGHT_GRAY)
                        cell.font = Font(name="Calibri", size=11, bold=True, color=BLACK)
            for r in range(top + 1, bottom + 1):
                if "severity" in headers and ws.title == "Issues":
                    colour = SEVERITY_COLORS.get(ws.cell(r, headers["severity"]).value, WHITE)
                    for c in range(left, right + 1):
                        ws.cell(r, c).fill = PatternFill("solid", fgColor=colour)
                code_field = "system_code" if "system_name" in headers else "code"
                name_field = "system_name" if "system_name" in headers else "name"
                if code_field in headers and name_field in headers:
                    code = str(ws.cell(r, headers[code_field]).value)
                    cell = ws.cell(r, headers[name_field])
                    if code in names and cell.value != names[code]:
                        renamed.append(
                            dict(sheet=ws.title, code=code, before=cell.value, after=names[code])
                        )
                        cell.value = names[code]
        for row in ws:
            for cell in row:
                if (
                    cell.value
                    == "VBA has not been executed in Windows Excel in this cloud delivery."
                ):
                    cell.value = (
                        "For the recorded Windows Excel session, see docs/windows_acceptance.md."
                    )
        for rules in ws.conditional_formatting._cf_rules.values():
            for rule in rules:
                if rule.dataBar:
                    rule.dataBar.color = "A6A6A6"
        ws.print_options.horizontalCentered = False
    workbook.properties = DocumentProperties(
        creator="DocTreeQA",
        lastModifiedBy="DocTreeQA",
        title="Reviewed documentation QA presentation copy",
        description="Synthetic data; review values preserved; presentation styling updated.",
    )
    workbook.custom_doc_props = CustomPropertyList()
    return renamed


def make_views(snapshot, folder):
    folder.mkdir(parents=True, exist_ok=True)
    views = {
        "issues_review": ("Issues", "A1:F12", 6),
        "manual_review": ("Manual Review", "A1:I8", 9),
        "review_audit": ("Change Log", "A1:F28", 6),
        "system_summary": ("System Summary", "A1:G23", 7),
    }
    for name, (sheet, area, columns) in views.items():
        wb = load_workbook(snapshot)
        for other in list(wb):
            if other.title != sheet:
                wb.remove(other)
        ws = wb[sheet]
        for merged in list(ws.merged_cells.ranges):
            if merged.min_row <= 3:
                row = merged.min_row
                ws.unmerge_cells(str(merged))
                ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=columns)
        ws.print_area = area
        ws.print_title_rows = "1:5"
        ws.page_setup.orientation = "landscape"
        ws.page_setup.paperSize = ws.PAPERSIZE_A3
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 1
        ws.page_margins.left = ws.page_margins.right = 0.2
        ws.page_margins.top = ws.page_margins.bottom = 0.2
        ws.oddFooter.center.text = ""
        ws.freeze_panes = None
        if name == "review_audit":
            for r in range(6, 22):
                ws.row_dimensions[r].hidden = True
        wb.save(folder / f"{name}.xlsx")
        wb.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--styled-copy", type=Path, required=True)
    parser.add_argument("--render-dir", type=Path)
    args = parser.parse_args()
    source = args.input.resolve()
    if args.styled_copy.resolve() == source:
        raise ValueError("Keep the uploaded source unchanged; use a separate output path")
    names = {
        r["code"]: r["name"]
        for r in read_csv(ROOT / "data/equipment_tree.csv", ["code", "name"])
        if r["level"] == "System"
    }
    original_hash = digest(source)
    original_vba = macro_digest(source)
    original = load_workbook(source, keep_vba=True)
    before = {
        ws.title: {(c.coordinate): c.value for row in ws for c in row if c.value is not None}
        for ws in original
    }
    renamed = restyle(original, names)
    original.save(args.styled_copy)
    original.close()
    assert digest(source) == original_hash
    assert macro_digest(args.styled_copy) == original_vba
    public = load_workbook(args.styled_copy, keep_vba=False)
    snapshot = ROOT / "reports/reviewed_snapshot.xlsx"
    public.save(snapshot)
    changes = []
    for ws in public:
        for coordinate, value in before[ws.title].items():
            after = ws[coordinate].value
            if after != value and not (value == "" and after is None):
                changes.append(dict(sheet=ws.title, cell=coordinate, before=value, after=after))
                assert after in names.values() or value.startswith("VBA has not been executed")
    assert public["Manual Review"]["B6"].value == "Rejected"
    assert public["Manual Review"]["P6"].value == "Dismissed"
    assert public["Issues"]["L6"].value == "Dismissed"
    assert public["System Summary"]["G23"].value == 199
    assert public["Change Log"].max_row - 5 == 23
    public.close()
    with zipfile.ZipFile(snapshot) as archive:
        assert not any("vbaProject" in name for name in archive.namelist())
    manifest = dict(
        source_filename=source.name,
        source_sha256=original_hash,
        source_vba_sha256=original_vba,
        source_unchanged=True,
        snapshot=snapshot.name,
        snapshot_sha256=digest(snapshot),
        snapshot_contains_macros=False,
        styled_copy_vba_preserved=True,
        renamed_system_labels=renamed,
        value_changes=changes,
        retained_review=dict(decision="Rejected", status="Dismissed", open_total=199, log_rows=23),
        presentation=(
            "White background, black text and thin black borders; warning/error hints retained"
        ),
        privacy=(
            "Personal document properties removed; original macro-enabled workbook not published"
        ),
        rendering="Selected ranges from the reviewed snapshot; not a new Windows macro execution",
        embedded_module_note=(
            "Styled user copy retains the tested original macro; "
            "import the updated .bas for future plain summaries"
        ),
        blank_cell_note="Empty text cells may roundtrip as blank cells",
    )
    # Only current display names are public; the original source is retained privately.
    for item in manifest["renamed_system_labels"]:
        item.pop("before")
    for item in manifest["value_changes"]:
        item.pop("before")
    (ROOT / "reports/review_snapshot_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    if args.render_dir:
        make_views(snapshot, args.render_dir)
    print(
        json.dumps(
            {
                "snapshot": str(snapshot),
                "styled_copy": str(args.styled_copy),
                "review_values_preserved": True,
                "vba_binary_preserved": True,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
