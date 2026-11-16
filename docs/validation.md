# Validation scope

The saved pytest XML and Ruff logs describe local Python checks. The independent
revalidation record confirms that saved source hashes match, finding identities
agree with the injection log, and safe changes replay to the cleaned register.

Workbook tests load the generated `.xlsx` with openpyxl. They check table schemas,
row counts, source values, summary totals, hierarchy order, numeric percentages,
text preservation and behavior with empty findings or malformed trees. The
initial workbook contains no VBA project or external links. Existing workbooks
are preserved unless `report --force` is explicitly requested.

The workbook was also rendered through LibreOffice for a visual layout check.
The cloud preview is an image of that rendered workbook, not a Windows Excel
screen or an illustration of a macro run.

## Optional VBA syntax check

`reports/vba_syntax_check.json` records a syntax parse of the actual exported
module with ANTLR and the public grammars-v4 VBA grammar. It includes the source
hash, pinned grammar blob identities and parser JAR hash. An intentionally
invalid module is checked too, to confirm that the parser rejects bad syntax.

To repeat this optional check, obtain the ANTLR complete JAR from
[the official download](https://www.antlr.org/download/antlr-4.13.2-complete.jar)
and the matching `vbaLexer.g4` and `vbaParser.g4` files from
[grammars-v4](https://github.com/antlr/grammars-v4/tree/master/vba/vba7_1).
The script verifies the exact blob identities recorded in its source; a newer
grammar revision will be rejected. The GitHub blob API can retrieve those exact
versions if the default branch has changed. The JDK must provide the Java
compiler module as well as the Java runtime.

```sh
uv run python scripts/check_vba_syntax.py --grammar-dir /path/to/grammar --antlr-jar /path/to/antlr.jar
```

This optional tool does not add a Java requirement to the Python CLI or Excel
review workflow. It checks language grammar only. It does not bind Excel object
types, compile the project in Excel or execute any VBA behavior. Pytest also
checks that macro table and column references exist in an actual workbook.

## Recorded Windows Excel acceptance

The user completed a desktop Excel session and supplied screenshots and a
written report. The main workflow passed: no compile error was reported, issue
highlighting ran, review decisions were logged, both matching statuses were
dismissed on rejection, and the open total remained 199 after reopening.
See `windows_acceptance.md` and `reports/windows_excel_acceptance.json`.

The session was performed by the user, not in Python CI or this environment.
The reviewed workbook binary and original image files were not supplied as
workspace files. Additional selection and cancellation cases were reported
successful overall but were not individually itemized. No stronger automated
runtime or binary inspection claim is made.

Python reference counts remain expectations, while the separately recorded
Windows observations describe the actual reported session. The syntax check
record's not-run fields refer to that grammar check, which never executes Excel.
