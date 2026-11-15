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

## Windows Excel acceptance remains pending

The exported module and the import instructions are ready. The definitive VBA
checks are **Debug > Compile VBAProject**, the macro behavior checks and a
save/reopen check in desktop Excel on Windows. None has been observed in the
cloud environment. Follow `excel_walkthrough.md` and record results in
`windows_acceptance.md`.

Python reference counts allow an observer to compare the macro's System Summary
with known expectations. They must not be described as macro execution evidence.
