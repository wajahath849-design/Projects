# AI Model Analytics Power BI Project

Open **AI Model Analytics.pbip** in Power BI Desktop.

The four dashboard pages are:
- Executive Overview
- Live Prediction
- Model Performance
- Data Explorer

Each page has the same four working navigation buttons and a matching page
heading. Use Ctrl+click on a button while editing in Power BI Desktop.

Connection:
- Server: localhost,14330
- Database: AIModelAnalytics
- Authentication: Windows
- Storage mode: DirectQuery
- Automatic page refresh: every 5 seconds

On first open, approve the native database connection. Visuals query SQL Server directly
and each active report page checks for new rows every 5 seconds.
The Model Name slicers control all model-specific visuals and accuracy cards.
This report is delivered in Power BI Project format because the installed Power BI
Desktop build exposes only **Power BI project files (.pbip)** when this project is
saved. Open the PBIP directly; it is the editable native project.

If visuals are blank:
1. Close every open copy of this report without saving.
2. Reopen AI Model Analytics.pbip from this folder.
3. Select Home > Transform data > Data source settings.
4. Edit the SQL Server permission and choose Windows authentication.
5. If Power BI reports a certificate error, clear the Encrypt connection option for this local SQLEXPRESS instance.
6. Select Home > Refresh.

If the latest image is blank:
1. Run `START_PROJECT.bat` from the main project folder before opening Power BI.
2. Confirm that `http://127.0.0.1:8000/latest-image` opens without a sign-in.
3. Reopen the report or select Home > Refresh so the image visual retries the URL.

The original and processed images are delivered by the local API on port 8000.
Power BI cannot display them while that service is stopped.
