from app.document_ingestion import parse_supplier_document
from app.external_signals import _read_json_path


def test_supplier_document_parser_extracts_core_fields() -> None:
    content = """
    INVOICE
    Invoice No: INV-2026-0042
    Purchase Order No: PO-77881
    Invoice Date: 2026-07-20
    Grand Total: EUR 1,245.50
    """
    parsed = parse_supplier_document(content)
    assert parsed["document_type"] == "INVOICE"
    assert parsed["document_number"] == "INV-2026-0042"
    assert parsed["purchase_order_no"] == "PO-77881"
    assert parsed["total_amount"] == "1,245.50"


def test_json_path_reader_supports_lists() -> None:
    payload = {"hourly": {"values": [{"delay": 2.5}]}}
    assert _read_json_path(payload, "hourly.values.0.delay") == 2.5
