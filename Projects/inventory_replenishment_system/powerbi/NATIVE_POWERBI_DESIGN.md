# Native Power BI Design Guide

## Page structure

- Canvas: `#F4F7FB`
- Header: `#0B1F33`
- Header accent: `#00A6A6`
- Visual panel: white
- Panel border: `#D7E0EA`
- Primary text: `#1F2937`
- Secondary text: `#64748B`

## Native design object names

Each page has the following editable objects, where `p1` through `p6` identify the page:

- `pX_native_header`
- `pX_native_accent`
- `pX_native_icon`
- `pX_native_footer_line`
- `pX_native_footer_left`
- `pX_native_footer_right`

The original page title object remains `pX_title`.

## Add your logo

Use **Insert > Image** only for a company logo if desired. The dashboard itself does not depend on an image. Place the logo at the top-left and delete or hide `pX_native_icon`.

## Change the title

Select `pX_title`, double-click the text, and edit the title or subtitle. The text box has no background because the native header sits behind it.
