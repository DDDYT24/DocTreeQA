# Keep future summaries in the plain style

The black-border `.xlsm` copy returned with the project preserves the tested
embedded macro binary. Its cell formatting has changed, but the embedded code
has not. Running its old BuildSystemSummary would restore the older formatting.

To use the revised style on future macro runs:

1. Keep a backup of your review workbook, then open the black-border copy.
2. Press **Alt+F11**, then **Ctrl+R** to show Project Explorer.
3. Under that workbook's **Modules**, right-click **DocTreeQA** and choose
   **Remove DocTreeQA**. Export a backup if desired.
4. Choose **File > Import File**, then select the current
   [DocTreeQA.bas](../vba/DocTreeQA.bas) from this project.
5. Choose **Debug > Compile VBAProject**, return to Excel and save the `.xlsm`.
6. Run **BuildSystemSummary**. The reviewed example should still total 199 and
   now use white cells, black text and black borders.

Only presentation code changed in the revised module. MarkReviewed and the
System counting logic were compared with the tested version and remain the
same. Syntax validation and rendering cover the new style; no new Windows
execution of this revised module is claimed.
