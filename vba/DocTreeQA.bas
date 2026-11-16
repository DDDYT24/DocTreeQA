Attribute VB_Name = "DocTreeQA"
Option Explicit

' Import into a review COPY of doctree_report.xlsx and save as .xlsm.
' All workbook references are anchored to ThisWorkbook, never another active file.
' Accepted retains an Open finding. Rejected dismisses the finding.
' No macro corrects document metadata or deletes a finding.

Private Const ERROR_BASE As Long = vbObjectError + 2100
Private Const SUMMARY_SHEET As String = "System Summary"
Private Const SUMMARY_TITLE As String = "DocTreeQA | System issue summary"

Private Function GetTable(ByVal sheetName As String, ByVal tableName As String) As ListObject
    On Error GoTo MissingTable
    Set GetTable = ThisWorkbook.Worksheets(sheetName).ListObjects(tableName)
    Exit Function
MissingTable:
    Err.Raise ERROR_BASE + 1, "DocTreeQA", _
        "Missing table '" & tableName & "' on '" & sheetName & "'. Use an unmodified report copy."
End Function

Private Sub RequireColumns(ByVal table As ListObject, ByVal names As Variant)
    Dim name As Variant
    Dim position As Long
    For Each name In names
        On Error GoTo MissingColumn
        position = table.ListColumns(CStr(name)).Index
        On Error GoTo 0
    Next name
    Exit Sub
MissingColumn:
    Err.Raise ERROR_BASE + 2, "DocTreeQA", _
        "Missing column '" & CStr(name) & "' in '" & table.Name & "'."
End Sub

Private Function FieldCell(ByVal entry As ListRow, ByVal name As String) As Range
    Dim table As ListObject
    Set table = entry.Parent
    Set FieldCell = entry.Range.Cells(1, table.ListColumns(name).Index)
End Function

Private Function CellText(ByVal cell As Range) As String
    If IsError(cell.Value2) Then
        Err.Raise ERROR_BASE + 3, "DocTreeQA", "A required cell contains an Excel error."
    End If
    CellText = CStr(cell.Value2)
End Function

Private Function FieldText(ByVal entry As ListRow, ByVal name As String) As String
    FieldText = CellText(FieldCell(entry, name))
End Function

Private Function FindingKey(ByVal entry As ListRow) As String
    Dim rule As String
    Dim kind As String
    Dim identity As String
    rule = FieldText(entry, "rule")
    kind = FieldText(entry, "entity_type")
    identity = FieldText(entry, "entity_id")
    If Len(rule) = 0 Or Len(kind) = 0 Or Len(identity) = 0 Then
        Err.Raise ERROR_BASE + 4, "DocTreeQA", "A finding has an empty identity."
    End If
    FindingKey = Len(rule) & ":" & rule & Len(kind) & ":" & kind & Len(identity) & ":" & identity
End Function

Private Sub WriteText(ByVal cell As Range, ByVal value As String)
    cell.NumberFormat = "@"
    cell.Value2 = value
End Sub

Public Sub HighlightIssues()
    Dim table As ListObject
    Dim entry As ListRow
    Dim color As Long
    Dim oldScreen As Boolean
    oldScreen = Application.ScreenUpdating
    On Error GoTo Failed
    Set table = GetTable("Issues", "IssuesTable")
    RequireColumns table, Array("severity")
    Application.ScreenUpdating = False
    table.ShowAutoFilter = True
    For Each entry In table.ListRows
        Select Case LCase$(Trim$(FieldText(entry, "severity")))
            Case "error": color = RGB(252, 228, 214)
            Case "warning": color = RGB(255, 242, 204)
            Case "info": color = RGB(231, 230, 230)
            Case Else: color = RGB(255, 255, 255)
        End Select
        entry.Range.Interior.Color = color
        entry.Range.Font.Color = RGB(0, 0, 0)
        With entry.Range.Borders
            .LineStyle = xlContinuous
            .Color = RGB(0, 0, 0)
            .Weight = xlThin
        End With
    Next entry
    Application.ScreenUpdating = oldScreen
    MsgBox "Issue rows coloured by severity; filter arrows are enabled.", vbInformation, "DocTreeQA"
    Exit Sub
Failed:
    Application.ScreenUpdating = oldScreen
    MsgBox Err.Description, vbExclamation, "DocTreeQA: HighlightIssues"
End Sub

Public Sub BuildSystemSummary()
    Dim issues As ListObject
    Dim completeness As ListObject
    Dim entry As ListRow
    Dim names As Object
    Dim groups As Object
    Dim counts As Variant
    Dim key As Variant
    Dim code As String
    Dim state As String
    Dim severity As String
    Dim ws As Worksheet
    Dim outputTable As ListObject
    Dim headers As Variant
    Dim index As Long
    Dim outputRow As Long
    Dim total As Long
    Dim oldScreen As Boolean
    oldScreen = Application.ScreenUpdating
    On Error GoTo Failed
    Set issues = GetTable("Issues", "IssuesTable")
    Set completeness = GetTable("Completeness", "CompletenessTable")
    RequireColumns issues, Array("system_code", "severity", "review_status")
    RequireColumns completeness, Array("code", "level", "name")
    Set names = CreateObject("Scripting.Dictionary")
    Set groups = CreateObject("Scripting.Dictionary")
    names.CompareMode = vbBinaryCompare
    groups.CompareMode = vbBinaryCompare
    For Each entry In completeness.ListRows
        If FieldText(entry, "level") = "System" Then
            code = FieldText(entry, "code")
            If Not names.Exists(code) Then
                names.Add code, FieldText(entry, "name")
                groups.Add code, Array(0&, 0&, 0&, 0&, 0&)
            End If
        End If
    Next entry
    ' Compute all counts before replacing the macro-owned summary sheet.
    For Each entry In issues.ListRows
        state = LCase$(Trim$(FieldText(entry, "review_status")))
        If state <> "open" And state <> "dismissed" Then
            Err.Raise ERROR_BASE + 5, "DocTreeQA", _
                "Unexpected review_status. Use Open or Dismissed before building the summary."
        End If
        If state = "open" Then
            code = FieldText(entry, "system_code")
            If Not names.Exists(code) Then
                code = "Unmapped / Unknown"
                If Not groups.Exists(code) Then
                    names.Add code, "No valid System assignment"
                    groups.Add code, Array(0&, 0&, 0&, 0&, 0&)
                End If
            End If
            counts = groups(code)
            severity = LCase$(Trim$(FieldText(entry, "severity")))
            Select Case severity
                Case "error": counts(0) = counts(0) + 1
                Case "warning": counts(1) = counts(1) + 1
                Case "info": counts(2) = counts(2) + 1
                Case Else: counts(3) = counts(3) + 1
            End Select
            counts(4) = counts(4) + 1
            groups(code) = counts
        End If
    Next entry
    On Error Resume Next
    Set ws = ThisWorkbook.Worksheets(SUMMARY_SHEET)
    On Error GoTo Failed
    If ws Is Nothing Then
        Set ws = ThisWorkbook.Worksheets.Add( _
            After:=ThisWorkbook.Worksheets(ThisWorkbook.Worksheets.Count))
        ws.Name = SUMMARY_SHEET
    ElseIf CellText(ws.Range("A1")) <> SUMMARY_TITLE Then
        Err.Raise ERROR_BASE + 6, "DocTreeQA", _
            "System Summary already exists and is not a DocTreeQA summary. Rename it first."
    End If
    Application.ScreenUpdating = False
    For index = ws.ListObjects.Count To 1 Step -1
        ws.ListObjects(index).Unlist
    Next index
    ws.Cells.UnMerge
    ws.Cells.Clear
    ws.Range("A1:G1").Merge
    WriteText ws.Range("A1"), SUMMARY_TITLE
    ws.Range("A1").Font.Size = 20
    ws.Range("A1").Font.Bold = True
    ws.Range("A1").Font.Color = RGB(0, 0, 0)
    ws.Range("A1:G1").Interior.Color = RGB(255, 255, 255)
    With ws.Range("A1:G1").Borders
        .LineStyle = xlContinuous
        .Color = RGB(0, 0, 0)
        .Weight = xlThin
    End With
    ws.Rows(1).RowHeight = 36
    ws.Range("A2:G2").Merge
    WriteText ws.Range("A2"), "SYNTHETIC DATA ONLY | Fictional metadata; no real ship or Seaspan data"
    ws.Range("A3:G3").Merge
    WriteText ws.Range("A3"), "Current Open findings. Accepted remains Open; Rejected is Dismissed."
    headers = Array("system_code", "system_name", "error", "warning", "info", "other", "total_open")
    For index = 0 To UBound(headers)
        WriteText ws.Cells(5, index + 1), CStr(headers(index))
    Next index
    outputRow = 6
    For Each key In groups.Keys
        WriteText ws.Cells(outputRow, 1), CStr(key)
        WriteText ws.Cells(outputRow, 2), CStr(names(key))
        counts = groups(key)
        For index = 0 To 4
            ws.Cells(outputRow, index + 3).Value2 = counts(index)
        Next index
        total = total + counts(4)
        outputRow = outputRow + 1
    Next key
    Set outputTable = ws.ListObjects.Add(xlSrcRange, ws.Range("A5:G" & (outputRow - 1)), , xlYes)
    outputTable.Name = "SystemSummaryTable"
    outputTable.TableStyle = ""
    outputTable.ShowTableStyleRowStripes = False
    outputTable.Range.Font.Name = "Calibri"
    outputTable.Range.Font.Size = 11
    outputTable.Range.Font.Color = RGB(0, 0, 0)
    outputTable.Range.Interior.Color = RGB(255, 255, 255)
    outputTable.HeaderRowRange.Interior.Color = RGB(242, 242, 242)
    outputTable.HeaderRowRange.Font.Bold = True
    With outputTable.Range.Borders
        .LineStyle = xlContinuous
        .Color = RGB(0, 0, 0)
        .Weight = xlThin
    End With
    WriteText ws.Cells(outputRow + 1, 1), "TOTAL OPEN"
    ws.Cells(outputRow + 1, 7).Value2 = total
    ws.Rows(outputRow + 1).Font.Bold = True
    ws.Columns("A").ColumnWidth = 24
    ws.Columns("B").ColumnWidth = 44
    ws.Columns("C:G").ColumnWidth = 16
    ws.Rows(5).RowHeight = 28
    Application.ScreenUpdating = oldScreen
    MsgBox "System Summary rebuilt. Total Open findings: " & total, vbInformation, "DocTreeQA"
    Exit Sub
Failed:
    Application.ScreenUpdating = oldScreen
    MsgBox Err.Description, vbExclamation, "DocTreeQA: BuildSystemSummary"
End Sub

Private Sub StageChange( _
    ByVal target As Range, ByVal afterValue As String, ByVal fieldLabel As String, _
    ByVal sourceId As String, ByVal docId As String, ByVal reason As String, _
    ByVal targets As Collection, ByVal beforeValues As Collection, _
    ByVal afterValues As Collection, ByVal auditRows As Collection)
    Dim beforeValue As String
    beforeValue = CellText(target)
    If beforeValue = afterValue Then Exit Sub
    targets.Add target
    beforeValues.Add beforeValue
    afterValues.Add afterValue
    auditRows.Add Array(sourceId, docId, fieldLabel, beforeValue, afterValue, reason)
End Sub

Public Sub MarkReviewed()
    Dim manual As ListObject
    Dim issues As ListObject
    Dim log As ListObject
    Dim entry As ListRow
    Dim issueEntry As ListRow
    Dim logEntry As ListRow
    Dim selected As Range
    Dim target As Range
    Dim chosen As Collection
    Dim targets As Collection
    Dim beforeValues As Collection
    Dim afterValues As Collection
    Dim auditRows As Collection
    Dim issueIndex As Object
    Dim key As String
    Dim decisionInput As Variant
    Dim initialsInput As Variant
    Dim decision As String
    Dim initials As String
    Dim status As String
    Dim stamp As String
    Dim reason As String
    Dim sourceId As String
    Dim docId As String
    Dim audit As Variant
    Dim auditFields As Variant
    Dim index As Long
    Dim column As Long
    Dim applied As Long
    Dim previousLogCount As Long
    Dim writing As Boolean
    Dim oldScreen As Boolean
    Dim oldEvents As Boolean
    Dim errorMessage As String
    oldScreen = Application.ScreenUpdating
    oldEvents = Application.EnableEvents
    On Error GoTo Failed
    Set manual = GetTable("Manual Review", "ManualReviewTable")
    Set issues = GetTable("Issues", "IssuesTable")
    Set log = GetTable("Change Log", "ChangeLogTable")
    RequireColumns manual, Array("review_id", "decision", "initials", "reviewed_at", _
        "rule", "entity_type", "entity_id", "row_id", "doc_id", "review_status")
    RequireColumns issues, Array("rule", "entity_type", "entity_id", "review_status")
    RequireColumns log, Array("row_id", "doc_id", "field", "before", "after", "reason")
    If Not (Application.ActiveWorkbook Is ThisWorkbook) Then
        Err.Raise ERROR_BASE + 7, "DocTreeQA", "Activate the report workbook first."
    End If
    If Not (Application.ActiveSheet Is manual.Parent) Then
        Err.Raise ERROR_BASE + 8, "DocTreeQA", "Select rows on Manual Review first."
    End If
    If Not (TypeOf Application.Selection Is Excel.Range) Then
        Err.Raise ERROR_BASE + 9, "DocTreeQA", "Select cells inside Manual Review."
    End If
    If manual.DataBodyRange Is Nothing Then
        MsgBox "No findings are available for review.", vbInformation, "DocTreeQA"
        Exit Sub
    End If
    Set selected = Application.Intersect(Application.Selection, manual.DataBodyRange)
    If selected Is Nothing Then
        Err.Raise ERROR_BASE + 10, "DocTreeQA", "Select data rows, not the title or header."
    End If
    Set chosen = New Collection
    For Each entry In manual.ListRows
        If Not entry.Range.EntireRow.Hidden Then
            If Not Application.Intersect(selected, entry.Range) Is Nothing Then chosen.Add entry
        End If
    Next entry
    If chosen.Count = 0 Then
        MsgBox "No visible selected data rows.", vbInformation, "DocTreeQA"
        Exit Sub
    End If
    decisionInput = Application.InputBox( _
        Prompt:="Type Accepted to retain the finding, or Rejected to dismiss it.", _
        Title:="DocTreeQA: review decision", Default:="Accepted", Type:=2)
    If VarType(decisionInput) = vbBoolean Then Exit Sub
    Select Case LCase$(Trim$(CStr(decisionInput)))
        Case "accepted": decision = "Accepted": status = "Open"
        Case "rejected": decision = "Rejected": status = "Dismissed"
        Case Else
            Err.Raise ERROR_BASE + 11, "DocTreeQA", "Enter Accepted or Rejected. No changes were made."
    End Select
    initialsInput = Application.InputBox( _
        Prompt:="Enter your initials (up to twelve characters).", Title:="DocTreeQA: reviewer", Type:=2)
    If VarType(initialsInput) = vbBoolean Then Exit Sub
    initials = Trim$(CStr(initialsInput))
    If Len(initials) = 0 Or Len(initials) > 12 Or InStr(initials, vbLf) > 0 _
        Or InStr(initials, vbCr) > 0 Then
        Err.Raise ERROR_BASE + 12, "DocTreeQA", "Enter valid initials. No changes were made."
    End If
    Set issueIndex = CreateObject("Scripting.Dictionary")
    issueIndex.CompareMode = vbBinaryCompare
    For Each issueEntry In issues.ListRows
        key = FindingKey(issueEntry)
        If issueIndex.Exists(key) Then
            Err.Raise ERROR_BASE + 13, "DocTreeQA", "Issues contains duplicate finding identities."
        End If
        issueIndex.Add key, issueEntry
    Next issueEntry
    Set targets = New Collection
    Set beforeValues = New Collection
    Set afterValues = New Collection
    Set auditRows = New Collection
    stamp = Format$(Now, "yyyy-mm-dd hh:nn:ss")
    ' Stage everything before changing either table. Filtered-out rows remain untouched.
    For Each entry In chosen
        key = FindingKey(entry)
        If Not issueIndex.Exists(key) Then
            Err.Raise ERROR_BASE + 14, "DocTreeQA", "A selected review row has no matching Issue."
        End If
        Set issueEntry = issueIndex(key)
        sourceId = FieldText(entry, "row_id")
        If Len(sourceId) = 0 Then sourceId = FieldText(entry, "entity_id")
        docId = FieldText(entry, "doc_id")
        reason = "VBA review " & FieldText(entry, "review_id") & "; " & initials & "; local " & stamp
        StageChange FieldCell(entry, "decision"), decision, "Manual Review.decision", _
            sourceId, docId, reason, targets, beforeValues, afterValues, auditRows
        StageChange FieldCell(entry, "initials"), initials, "Manual Review.initials", _
            sourceId, docId, reason, targets, beforeValues, afterValues, auditRows
        StageChange FieldCell(entry, "reviewed_at"), stamp, "Manual Review.reviewed_at", _
            sourceId, docId, reason, targets, beforeValues, afterValues, auditRows
        StageChange FieldCell(entry, "review_status"), status, "Manual Review.review_status", _
            sourceId, docId, reason, targets, beforeValues, afterValues, auditRows
        StageChange FieldCell(issueEntry, "review_status"), status, "Issues.review_status", _
            sourceId, docId, reason, targets, beforeValues, afterValues, auditRows
    Next entry
    previousLogCount = log.ListRows.Count
    Application.ScreenUpdating = False
    Application.EnableEvents = False
    writing = True
    auditFields = Array("row_id", "doc_id", "field", "before", "after", "reason")
    For index = 1 To targets.Count
        Set target = targets(index)
        WriteText target, CStr(afterValues(index))
        applied = index
    Next index
    For index = 1 To auditRows.Count
        Set logEntry = log.ListRows.Add
        audit = auditRows(index)
        For column = 0 To UBound(audit)
            WriteText logEntry.Range.Cells(1, log.ListColumns(CStr(auditFields(column))).Index), _
                CStr(audit(column))
        Next column
    Next index
    Application.EnableEvents = oldEvents
    Application.ScreenUpdating = oldScreen
    MsgBox chosen.Count & " visible review row(s) marked " & decision & _
        ". Rebuild System Summary to refresh current counts.", vbInformation, "DocTreeQA"
    Exit Sub
Failed:
    errorMessage = Err.Description
    If writing Then
        ' Roll back value changes and appended audit rows if a write fails.
        On Error Resume Next
        For index = applied To 1 Step -1
            Set target = targets(index)
            WriteText target, CStr(beforeValues(index))
        Next index
        For index = log.ListRows.Count To previousLogCount + 1 Step -1
            log.ListRows(index).Delete
        Next index
        On Error GoTo 0
        errorMessage = errorMessage & " Review writes were rolled back where possible; inspect the copy."
    End If
    Application.EnableEvents = oldEvents
    Application.ScreenUpdating = oldScreen
    MsgBox errorMessage, vbExclamation, "DocTreeQA: MarkReviewed"
End Sub
