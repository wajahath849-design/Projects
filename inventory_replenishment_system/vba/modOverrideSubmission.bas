Attribute VB_Name = "modOverrideSubmission"
Option Explicit

Public Sub SubmitOverrideFromSheet()
    On Error GoTo ErrorHandler

    Dim warehouseCode As String, skuCode As String, overrideType As String
    Dim reason As String, submittedBy As String, effectiveFromUtc As String, effectiveToUtc As String
    Dim numericValue As Variant, textValue As Variant
    Dim pythonExe As String, projectRoot As String, apiUrl As String
    Dim payloadPath As String, resultPath As String, jsonPayload As String, commandLine As String
    Dim shell As Object, fileSystem As Object, tempFolder As String, stamp As String

    warehouseCode = UCase$(Trim$(CStr(NamedValue("inpWarehouseCode"))))
    skuCode = UCase$(Trim$(CStr(NamedValue("inpSkuCode"))))
    overrideType = UCase$(Trim$(CStr(NamedValue("inpOverrideType"))))
    numericValue = NamedValue("inpNumericValue")
    textValue = NamedValue("inpTextValue")
    effectiveFromUtc = IsoUtcString(NamedValue("inpEffectiveFromUTC"))
    effectiveToUtc = IsoUtcString(NamedValue("inpEffectiveToUTC"))
    reason = Trim$(CStr(NamedValue("inpReason")))
    submittedBy = Trim$(CStr(NamedValue("inpSubmittedBy")))

    If Not IsValidCode(warehouseCode, 2, 40) Then Err.Raise vbObjectError + 1200, , "Invalid warehouse code."
    If Not IsValidCode(skuCode, 3, 80) Then Err.Raise vbObjectError + 1201, , "Invalid SKU code."
    If effectiveFromUtc = vbNullString Then Err.Raise vbObjectError + 1202, , "Effective From UTC is required."
    If Len(reason) < 5 Then Err.Raise vbObjectError + 1203, , "Reason must contain at least five characters."
    If Len(submittedBy) < 2 Then Err.Raise vbObjectError + 1204, , "Submitted By is required."
    If Trim$(CStr(numericValue)) = vbNullString And Trim$(CStr(textValue)) = vbNullString Then
        Err.Raise vbObjectError + 1205, , "Enter either a numeric value or a text value."
    End If

    Select Case overrideType
        Case "PHYSICAL_COUNT", "SAFETY_STOCK", "REORDER_QTY"
            If Not IsNumeric(numericValue) Or CDbl(numericValue) < 0 Then
                Err.Raise vbObjectError + 1206, , overrideType & " requires a non-negative numeric value."
            End If
        Case "DEMAND_MULTIPLIER"
            If Not IsNumeric(numericValue) Or CDbl(numericValue) < 0 Or CDbl(numericValue) > 10 Then
                Err.Raise vbObjectError + 1207, , "Demand multiplier must be between 0 and 10."
            End If
        Case "LEAD_TIME_PENALTY"
            If Not IsNumeric(numericValue) Or CDbl(numericValue) < 0 Or CDbl(numericValue) > 365 Then
                Err.Raise vbObjectError + 1208, , "Lead-time penalty must be between 0 and 365 days."
            End If
        Case "HOLD_REPLENISHMENT"
            If Trim$(CStr(textValue)) = vbNullString Then textValue = "true"
        Case Else
            Err.Raise vbObjectError + 1209, , "Unsupported override type."
    End Select

    pythonExe = Trim$(CStr(NamedValue("cfgPythonExe")))
    projectRoot = Trim$(CStr(NamedValue("cfgProjectRoot")))
    apiUrl = Trim$(CStr(NamedValue("cfgApiUrl")))
    If Dir$(pythonExe) = vbNullString Then Err.Raise vbObjectError + 1210, , "Python executable not found: " & pythonExe
    If Dir$(projectRoot, vbDirectory) = vbNullString Then Err.Raise vbObjectError + 1211, , "Project root not found: " & projectRoot

    jsonPayload = "{" & _
        """warehouse_code"":""" & JsonEscape(warehouseCode) & """," & _
        """sku_code"":""" & JsonEscape(skuCode) & """," & _
        """override_type"":""" & JsonEscape(overrideType) & """," & _
        """numeric_value"":" & JsonNumberOrNull(numericValue) & "," & _
        """text_value"":" & JsonStringOrNull(textValue) & "," & _
        """effective_from"":""" & effectiveFromUtc & """," & _
        """effective_to"":" & IIf(effectiveToUtc = vbNullString, "null", """" & effectiveToUtc & """") & "," & _
        """reason"":""" & JsonEscape(reason) & """," & _
        """submitted_by"":""" & JsonEscape(submittedBy) & """}"

    Set fileSystem = CreateObject("Scripting.FileSystemObject")
    tempFolder = fileSystem.GetSpecialFolder(2).Path
    stamp = Format$(Now, "yyyymmdd_hhnnss") & "_" & Format$(CLng(Timer * 100), "00000000")
    payloadPath = tempFolder & "\inventory_override_" & stamp & ".json"
    resultPath = tempFolder & "\inventory_override_" & stamp & ".result.json"
    WriteUtf8TextFile payloadPath, jsonPayload

    commandLine = """" & pythonExe & """ -m app.excel_bridge --payload """ & payloadPath & _
                  """ --api-url """ & apiUrl & """ --result """ & resultPath & """"
    Set shell = CreateObject("WScript.Shell")
    shell.CurrentDirectory = projectRoot
    shell.Run commandLine, 0, False

    SetNamedValue "cfgLastResultPath", resultPath
    SetNamedValue "cfgPollCount", 0
    SetNamedValue "outSubmissionStatus", "Submitted in background at " & Format$(Now, "yyyy-mm-dd HH:nn:ss")
    Application.OnTime Now + TimeSerial(0, 0, 3), "PollLastSubmissionResult"
    Exit Sub

ErrorHandler:
    On Error Resume Next
    SetNamedValue "outSubmissionStatus", "ERROR: " & Err.Description
    MsgBox Err.Description, vbExclamation, "Override submission"
End Sub

Public Sub PollLastSubmissionResult()
    On Error GoTo PollAgain
    Dim resultPath As String, content As String, pollCount As Long
    resultPath = Trim$(CStr(NamedValue("cfgLastResultPath")))
    pollCount = CLng(NamedValue("cfgPollCount")) + 1
    SetNamedValue "cfgPollCount", pollCount
    If pollCount > 20 Then
        SetNamedValue "outSubmissionStatus", "TIMEOUT: No result file was produced. Check Python and API logs."
        Exit Sub
    End If
    If resultPath = vbNullString Then Exit Sub
    If Dir$(resultPath) = vbNullString Then GoTo PollAgain

    content = ReadTextFile(resultPath)
    If InStr(1, content, """ok"": true", vbTextCompare) > 0 Then
        SetNamedValue "outSubmissionStatus", "SUCCESS: Override saved and awaiting approval."
    Else
        SetNamedValue "outSubmissionStatus", "FAILED: " & Left$(content, 500)
    End If
    Exit Sub

PollAgain:
    Application.OnTime Now + TimeSerial(0, 0, 3), "PollLastSubmissionResult"
End Sub
