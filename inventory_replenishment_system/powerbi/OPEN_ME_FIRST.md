# Inventory Control Tower — Native Power BI Project

This package is an editable Power BI Project (`.pbip`) built without SVG page backgrounds.

## What is native

- Header and accent strip: Power BI text boxes with editable backgrounds
- Page titles and subtitles: Power BI text boxes
- KPI cards: native Power BI card visuals
- Charts: native Power BI bar, column, line and donut visuals
- Tables: native Power BI table visuals
- Filters: native Power BI slicers
- White panels, borders and shadows: native visual-container formatting
- Footer labels: editable Power BI text boxes
- Colours and typography: Power BI JSON theme

No SVG or page-background image is required.

## Open and refresh

1. Start the inventory backend with `docker compose up -d`.
2. Extract this package to a normal local folder.
3. Double-click `Inventory_Control_Tower.pbip`.
4. Enter the PostgreSQL database credentials from the backend `.env` file.
5. Select **Home > Refresh**.
6. Save the project. Use **File > Save As** in Power BI Desktop to create a `.pbix` copy.

## Default connection

- Server: `localhost:5432`
- Database: `inventory`
- Authentication: Database
- Username: normally `inventory_app`
- Password: the value of `POSTGRES_PASSWORD` in `.env`

No password is embedded in the project.

## Editing the design

Every visible design element can be selected and changed in Power BI Desktop. Use **View > Selection** to rename, hide, reorder or delete the native header, accent strip, icon and footer text boxes.
