Attribute VB_Name = "modPurchaseOrder"
Option Explicit

Public Sub GenerateAndEmailPurchaseOrder()
    On Error GoTo ErrorHandler

    Dim poSheet As Worksheet
    Dim purchaseOrderNo As String, supplierEmail As String, supplierName As String
    Dim outputFolder As String, pdfPath As String
    Dim approved As Boolean, autoSend As Boolean
    Dim outlookApp As Object, mailItem As Object

    Set poSheet = ThisWorkbook.Worksheets("Purchase_Order")
    purchaseOrderNo = Trim$(CStr(NamedValue("poNumber")))
    supplierEmail = Trim$(CStr(NamedValue("poSupplierEmail")))
    supplierName = Trim$(CStr(NamedValue("poSupplierName")))
    outputFolder = Trim$(CStr(NamedValue("cfgPurchaseOrderFolder")))
    approved = CBool(NamedValue("poApproved"))
    autoSend = CBool(NamedValue("poAutoSend"))

    If Not approved Then Err.Raise vbObjectError + 1300, , "The purchase order must be approved before PDF generation."
    If purchaseOrderNo = vbNullString Then Err.Raise vbObjectError + 1301, , "Purchase order number is missing."
    If supplierEmail = vbNullString Or InStr(1, supplierEmail, "@") = 0 Then
        Err.Raise vbObjectError + 1302, , "Supplier email is invalid."
    End If
    If Dir$(outputFolder, vbDirectory) = vbNullString Then MkDir outputFolder

    pdfPath = outputFolder & "\" & purchaseOrderNo & ".pdf"
    poSheet.ExportAsFixedFormat _
        Type:=xlTypePDF, _
        Filename:=pdfPath, _
        Quality:=xlQualityStandard, _
        IncludeDocProperties:=True, _
        IgnorePrintAreas:=False, _
        OpenAfterPublish:=False

    Set outlookApp = CreateObject("Outlook.Application")
    Set mailItem = outlookApp.CreateItem(0)
    With mailItem
        .To = supplierEmail
        .Subject = "Purchase Order " & purchaseOrderNo
        .HTMLBody = "<p>Dear " & HtmlEncode(supplierName) & ",</p>" & _
                    "<p>Please find attached purchase order <strong>" & HtmlEncode(purchaseOrderNo) & _
                    "</strong>. Please confirm availability and expected delivery date.</p>" & _
                    "<p>Regards,<br>Supply Chain Operations</p>"
        .Attachments.Add pdfPath
        If autoSend Then
            .Send
        Else
            .Display
        End If
    End With

    SetNamedValue "outPOStatus", IIf(autoSend, "PO emailed: ", "PO prepared for review: ") & pdfPath
    Exit Sub

ErrorHandler:
    On Error Resume Next
    SetNamedValue "outPOStatus", "ERROR: " & Err.Description
    MsgBox Err.Description, vbExclamation, "Purchase order"
End Sub

Private Function HtmlEncode(ByVal value As String) As String
    value = Replace(value, "&", "&amp;")
    value = Replace(value, "<", "&lt;")
    value = Replace(value, ">", "&gt;")
    value = Replace(value, Chr$(34), "&quot;")
    HtmlEncode = value
End Function
