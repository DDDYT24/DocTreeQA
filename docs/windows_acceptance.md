# Windows Excel acceptance record

Status: **MAIN WORKFLOW PASSED**, based on the user's report and screenshots from
a Windows desktop Excel session. Python CI does not execute these macros.

| Environment | Observed value |
| --- | --- |
| Windows version | Windows desktop; exact version not supplied |
| Excel version and bitness | Microsoft Excel for Microsoft 365 MSO, version 2610, build 16.0.20527.20196, 64 bit |
| Test date and local timezone | 2026-11-15; local timezone not supplied |
| Review-copy filename | Not supplied; reviewed workbook binary not received |
| Source commit or ZIP | Earlier report with letter-based System labels; exact archive not supplied |

| Check | Observed result | Evidence |
| --- | --- | --- |
| Import module into the intended workbook | Passed by user report and subsequent execution | Macro success dialog and review log |
| Debug > Compile VBAProject | Passed by user report | No compilation error; macros subsequently ran |
| HighlightIssues recolours rows and enables filters | Passed by screenshot | Success dialog, coloured rows and filter arrows |
| BuildSystemSummary matches the saved reference after rejection | Passed by screenshot and numeric comparison | Total 199; System 240 reduced by one; unmapped total 16 |
| Rebuilding the summary before review is repeatable | Reported successful overall, not itemized | No individual observation supplied |
| Accepted stamps the selected row and retains Open | Passed by review log evidence | Pending to Accepted; initials and timestamp populated |
| Rejected dismisses the matching finding | Passed by screenshot log and user report | Accepted to Rejected; both review statuses Open to Dismissed; user confirmed P6 |
| Review changes append to Change Log | Passed by screenshot | Seven added audit rows record the accepted and rejected decisions |
| Filtered hidden rows remain unchanged | Reported successful overall, not itemized | No individual observation supplied |
| Cancellation leaves values unchanged | Reported successful overall, not itemized | No individual observation supplied |
| Wrong-sheet selection leaves values unchanged | Reported successful overall, not itemized | No individual observation supplied |
| Save and reopen retains macros and decisions | Passed by user report | Summary after reopening remains 199 |

The machine-readable observations are in `reports/windows_excel_acceptance.json`.
System totals transcribed from the supplied image are in
`reports/windows_review_observed.csv`. The original generated register remains
unchanged with its baseline open findings; reviewer actions belong to the
separate review copy.

The repository module hash is recorded, but the reviewed copy's module hash is
unknown because the workbook binary was not supplied. Earlier System labels
are a report naming difference; the module source is unchanged.

Original screenshot files have not yet been archived in the repository. The
version dialog is excluded from public images, and the earlier System Summary
image is represented only by transcribed numeric counts. Product version, build
and bitness were recorded without license or session identifiers.
