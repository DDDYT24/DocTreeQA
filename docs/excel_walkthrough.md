# Windows Excel import and acceptance

This guide is for desktop Excel on Windows. The workbook is an `.xlsx` file
without embedded macros. The exported module is `vba/DocTreeQA.bas`.
Python checks and syntax validation do not establish that VBA runs in Excel.
Complete and record the steps below before claiming Windows Excel validation.

## Open a review copy

1. Extract the project ZIP to a normal folder, then open
   `reports/doctree_report.xlsx` in desktop Excel.
2. Click **File > Save As > Browse**. In **Save as type**, choose
   **Excel Macro-Enabled Workbook (*.xlsm)**. Name the copy
   `doctree_review.xlsm` and click **Save**. Keep the original `.xlsx` unchanged.
3. To show the Developer tab, click **File > Options > Customize Ribbon**.
   Check **Developer** in the right list, then click **OK**.
4. Click **Developer > Visual Basic**, or press **Alt+F11**.
5. If Project Explorer is hidden, press **Ctrl+R**. Select
   **VBAProject (doctree_review.xlsm)**, then click **File > Import File**.
   Select `vba/DocTreeQA.bas` from the extracted project. A module named
   **DocTreeQA** should appear under **Modules** in that project.
6. Click **Debug > Compile VBAProject**. Record any compile error exactly.
   A successful compile has no error dialog; the Compile command may then be
   disabled until code changes. Do not count import alone as a successful test.
7. Press **Ctrl+S**, then **Alt+Q** to return to Excel. If Excel shows a macro
   notification for this review copy, follow its per-file enable-content action.

## Test HighlightIssues

1. Open **Issues**. To make the test observable, select **A6** and use
   **Home > Fill Color > No Fill** to remove that row's existing fill in the
   selected cell. This only changes formatting in your review copy.
2. Press **Alt+F8**, choose **DocTreeQA.HighlightIssues** (or
   **HighlightIssues**, depending on Excel's display), and click **Run**.
3. Check that the selected error cell is recoloured. Errors are pale red,
   warnings pale yellow and informational issues pale blue. Filter arrows
   should be visible in the Issues table header. No metadata should change.
4. Filter the **severity** column to `warning` to inspect warning rows, then
   clear that filter before continuing.

## Test BuildSystemSummary

1. Press **Alt+F8**, choose **BuildSystemSummary**, and click **Run**.
2. Open the new **System Summary** sheet. Compare every System row and the
   **Unmapped / Unknown** row with `reports/system_summary_expected.csv`.
   Use `reports/excel_acceptance_reference.json` for the expected total.
3. Run the macro again. The same sheet should be rebuilt without duplicate
   rows or sheets. Systems without open findings should still be present.

Only a sheet bearing the macro's own title is replaced. An unrelated sheet
already named System Summary must be renamed before the macro can create its
output. Counts use the current Issues table. Unknown mappings have their own
row and are not silently omitted.

## Test MarkReviewed

1. Open **Manual Review**. Click the **Name Box** to the left of the formula
   bar, type `A6`, and press **Enter** to select the first data row.
2. Press **Alt+F8**, select **MarkReviewed**, and click **Run**.
3. In the first prompt, type `Accepted` and click **OK**. In the next prompt,
   type your initials and click **OK**.
4. Check the selected row: **decision** is Accepted, **initials** contains your
   initials, and **reviewed_at** contains your local Excel date and time.
   Both its **review_status** and the corresponding Issues finding remain
   Open. Match findings by **rule**, **entity_type** and **entity_id**, not by
   document ID alone. Some findings concern equipment or document requirements.
5. Check **Change Log**. New rows should record the reviewer fields' before
   and after values, the review ID, initials and local timestamp in the reason.
6. Run **BuildSystemSummary** again. The open total must remain the value in
   `after_accepting_first_row` in the reference JSON.
7. Return to **Manual Review**, select `A6` again, and run **MarkReviewed**.
   Enter `Rejected` and the same initials. The decision should become Rejected,
   and both matching review statuses should become Dismissed.
8. Rebuild **System Summary**. Its total must match
   `after_rejecting_same_first_row` in the reference JSON. The underlying
   finding remains in Issues and the review queue, with its audit history.

Accepted means the finding is retained for follow-up; it does not mean the
underlying documentation problem is resolved. Rejected means the reviewer
dismisses the finding. A reviewer may change that decision later, with the
changed fields appended to the log.

The Summary sheet's original counts and the CSV/JSON outputs remain a generated
snapshot. Macros operate inside the `.xlsm` review copy only. Run
BuildSystemSummary after review to refresh current open counts. Typing into
review cells alone does not synchronize the Issues table; use MarkReviewed.

## Test selection, cancellation and saving

- With a filter active on Manual Review, select a range that includes hidden
  rows, run MarkReviewed, and confirm that only visible selected rows change.
  Disjoint selected cells in a row must produce a single review action.
- Run MarkReviewed and click **Cancel** at either prompt. Decisions, statuses
  and Change Log must remain unchanged.
- Try MarkReviewed while Issues is active. It should explain which sheet to
  select and leave the workbook unchanged.
- Save the review copy with **Ctrl+S**, close it, reopen it and rebuild System
  Summary. Verify that the module and reviewer decisions were retained.

## Evidence to record

Record the Windows version, Excel version from **File > Account > About Excel**,
test date, review-copy filename and pass/fail results in
`docs/windows_acceptance.md`. Keep the `.xlsm` copy with the evidence.

Capture real Windows Excel screenshots of Issues after highlighting, System
Summary, Manual Review after a decision, and the appended audit rows. Save them
under `docs/screenshots/` with clear names. The cloud-rendered workbook preview
is a layout check and is not evidence of macro execution.
