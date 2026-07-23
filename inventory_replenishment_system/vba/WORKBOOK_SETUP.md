# Excel workbook setup

Create an `.xlsm` workbook with these sheets:

- `Override_Form`
- `Purchase_Order`
- `Lists`
- `Config` (hide this sheet after configuration)

The supplied `Inventory_Operations_Template.xlsx` includes a `Config` field map, so workbook-level names are optional. The VBA first uses a workbook name and then falls back to the Config mapping. The mapped fields are:

## Configuration

- `cfgPythonExe` — full path to `.venv\Scripts\python.exe`
- `cfgProjectRoot` — full path to this project folder
- `cfgApiUrl` — normally `http://localhost:8000`
- `cfgLastResultPath` — blank helper cell
- `cfgPollCount` — numeric helper cell initialized to 0
- `cfgPurchaseOrderFolder` — approved PDF output folder

The API key is intentionally **not** stored in Excel. Create the Windows user environment variable `INVENTORY_API_KEY`.

## Override form

- `inpWarehouseCode`
- `inpSkuCode`
- `inpOverrideType`
- `inpNumericValue`
- `inpTextValue`
- `inpEffectiveFromUTC`
- `inpEffectiveToUTC`
- `inpReason`
- `inpSubmittedBy`
- `outSubmissionStatus`

Allowed override types:

`PHYSICAL_COUNT`, `DEMAND_MULTIPLIER`, `LEAD_TIME_PENALTY`, `SAFETY_STOCK`, `REORDER_QTY`, `HOLD_REPLENISHMENT`

Add a form button and assign `SubmitOverrideFromSheet`.

## Purchase order

- `poNumber`
- `poSupplierEmail`
- `poSupplierName`
- `poApproved` — TRUE/FALSE
- `poAutoSend` — keep FALSE during testing
- `outPOStatus`

Set the print area on `Purchase_Order`, then assign `GenerateAndEmailPurchaseOrder` to a button.

Import the three `.bas` modules into the VBA editor and paste `ThisWorkbook.txt` into the `ThisWorkbook` code module.
