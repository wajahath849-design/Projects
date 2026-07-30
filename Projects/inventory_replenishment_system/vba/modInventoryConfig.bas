Attribute VB_Name = "modInventoryConfig"
Option Explicit

Public Function NamedValue(ByVal rangeName As String) As Variant
    On Error GoTo UseFieldMap
    NamedValue = ThisWorkbook.Names(rangeName).RefersToRange.Value
    Exit Function
UseFieldMap:
    Err.Clear
    Dim target As Range
    Set target = ResolveMappedRange(rangeName)
    NamedValue = target.Value
End Function

Public Sub SetNamedValue(ByVal rangeName As String, ByVal value As Variant)
    On Error GoTo UseFieldMap
    ThisWorkbook.Names(rangeName).RefersToRange.Value = value
    Exit Sub
UseFieldMap:
    Err.Clear
    Dim target As Range
    Set target = ResolveMappedRange(rangeName)
    target.Value = value
End Sub

Private Function ResolveMappedRange(ByVal fieldName As String) As Range
    Dim configSheet As Worksheet, matchCell As Range
    Dim targetSheetName As String, targetAddress As String
    On Error GoTo MissingField
    Set configSheet = ThisWorkbook.Worksheets("Config")
    Set matchCell = configSheet.Columns(5).Find(What:=fieldName, LookIn:=xlValues, LookAt:=xlWhole, MatchCase:=False)
    If matchCell Is Nothing Then GoTo MissingField
    targetSheetName = CStr(configSheet.Cells(matchCell.Row, 6).Value)
    targetAddress = CStr(configSheet.Cells(matchCell.Row, 7).Value)
    Set ResolveMappedRange = ThisWorkbook.Worksheets(targetSheetName).Range(targetAddress)
    Exit Function
MissingField:
    Err.Raise vbObjectError + 1100, "ResolveMappedRange", "Missing workbook name or Config field mapping: " & fieldName
End Function

Public Function JsonEscape(ByVal value As String) As String
    value = Replace(value, "\", "\\")
    value = Replace(value, Chr$(34), "\" & Chr$(34))
    value = Replace(value, vbCrLf, "\n")
    value = Replace(value, vbCr, "\n")
    value = Replace(value, vbLf, "\n")
    value = Replace(value, vbTab, "\t")
    JsonEscape = value
End Function

Public Function JsonStringOrNull(ByVal value As Variant) As String
    If IsError(value) Or IsEmpty(value) Or Trim$(CStr(value)) = vbNullString Then
        JsonStringOrNull = "null"
    Else
        JsonStringOrNull = Chr$(34) & JsonEscape(CStr(value)) & Chr$(34)
    End If
End Function

Public Function JsonNumberOrNull(ByVal value As Variant) As String
    If IsError(value) Or IsEmpty(value) Or Trim$(CStr(value)) = vbNullString Then
        JsonNumberOrNull = "null"
    ElseIf Not IsNumeric(value) Then
        Err.Raise vbObjectError + 1102, "JsonNumberOrNull", "Expected a numeric value."
    Else
        JsonNumberOrNull = Replace(Format$(CDbl(value), "0.############"), Application.International(xlDecimalSeparator), ".")
    End If
End Function

Public Function IsoUtcString(ByVal value As Variant) As String
    If IsError(value) Or IsEmpty(value) Or Trim$(CStr(value)) = vbNullString Then
        IsoUtcString = vbNullString
    ElseIf Not IsDate(value) Then
        Err.Raise vbObjectError + 1103, "IsoUtcString", "Expected a UTC date/time value."
    Else
        IsoUtcString = Format$(CDate(value), "yyyy-mm-dd\THH:nn:ss") & "Z"
    End If
End Function

Public Function IsValidCode(ByVal value As String, ByVal minLength As Long, ByVal maxLength As Long) As Boolean
    Dim regex As Object
    Set regex = CreateObject("VBScript.RegExp")
    With regex
        .Pattern = "^[A-Z0-9][A-Z0-9_-]*$"
        .IgnoreCase = False
        .Global = False
    End With
    IsValidCode = (Len(value) >= minLength And Len(value) <= maxLength And regex.Test(value))
End Function

Public Function ReadTextFile(ByVal filePath As String) As String
    Dim stream As Object
    Set stream = CreateObject("ADODB.Stream")
    With stream
        .Type = 2
        .Charset = "utf-8"
        .Open
        .LoadFromFile filePath
        ReadTextFile = .ReadText
        .Close
    End With
End Function

Public Sub WriteUtf8TextFile(ByVal filePath As String, ByVal content As String)
    Dim stream As Object
    Set stream = CreateObject("ADODB.Stream")
    With stream
        .Type = 2
        .Charset = "utf-8"
        .Open
        .WriteText content
        .SaveToFile filePath, 2
        .Close
    End With
End Sub
