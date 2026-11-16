# Synthetic validation outputs

All records and results in this folder describe generated fictional metadata.
They do not represent real ship, Seaspan, or customer documents. There are no
underlying PDFs, drawings or document content in this project.

`summary.json` records the configured review date, counts, completeness, runtime
scope and SHA256 hashes of the inputs. `scoring.json` records per-rule precision
and recall against the separate injected-error log. A null metric means its
denominator is empty; it does not mean perfect performance.

`issues.csv` contains findings, and `manual_review.csv` contains the same findings
with empty reviewer fields. Every finding needs a human decision. None has been
resolved automatically. The safe changes in `change_log.csv` apply only to
`document_register_cleaned.csv`; the source register remains unchanged.

`completeness.csv` measures coverage of required types by mapped, issued metadata
records. It does not establish that document content is correct. The configured
equipment class is the first word of an equipment name. The tree trust flag in
the JSON summary must be checked before using the rollups.

The test XML files record local test runs. `publication.json` records the
publication status and requested target; `ci_status.json` records whether a
hosted workflow has run and the exact commit it tested. Consult that record
for the observed result and the repository Actions page for later runs.
The configured hosted checks exercise Python and static workbook contracts;
they do not run VBA.
`doctree_report.xlsx` is a macro-free Excel review workbook. Its source hashes,
sheet row counts and review semantics are saved in `workbook_manifest.json`.
`excel_acceptance_reference.json` and `system_summary_expected.csv` contain Python
reference values for a later Windows Excel test, not VBA execution results.

`vba_syntax_check.json` records grammar syntax validation only.
`windows_excel_acceptance.json` records a user-run Windows desktop Excel session
supported by supplied screenshots and a written report.
`windows_review_observed.csv` transcribes numeric System counts after rejection.
The supplied workbook binary was independently inspected after the main workflow
passed. Extra selection and cancellation cases were not individually documented.
`reviewed_snapshot.xlsx` is a macro-free presentation copy; the manifest records
its source hash and the formatting/name changes. Four rendered views illustrate
its saved review state. The original macro-enabled input is not published.

The generated macro-free workbook and Python reference files describe the
baseline dataset. They do not contain the user's review edits. The cloud
workbook preview checks generated layout only. License and session identifiers
are excluded from the public observations.
