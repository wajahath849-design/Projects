from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pdfplumber
from sqlalchemy import text
from sqlalchemy.orm import Session


class DocumentExtractionError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _extract_pdf_text(path: Path) -> tuple[str, str]:
    pages: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    text_content = "\n".join(pages).strip()
    if len(text_content) >= 80:
        return text_content, "PDF_TEXT"

    try:
        import pytesseract
        from pdf2image import convert_from_path
    except ImportError as exc:
        raise DocumentExtractionError(
            "The PDF appears scanned. Install requirements-ocr.txt and the Tesseract/Poppler system packages."
        ) from exc

    images = convert_from_path(path, dpi=250, fmt="png", thread_count=2)
    ocr_text = "\n".join(pytesseract.image_to_string(image, lang="eng") for image in images).strip()
    if len(ocr_text) < 20:
        raise DocumentExtractionError("OCR completed but did not produce usable text")
    return ocr_text, "OCR"


def _first_match(patterns: list[str], content: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, content, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip()
    return None


def parse_supplier_document(content: str) -> dict[str, Any]:
    normalized = re.sub(r"[ \t]+", " ", content)
    document_type = "UNKNOWN"
    lowered = normalized.lower()
    if "invoice" in lowered:
        document_type = "INVOICE"
    elif "packing slip" in lowered or "delivery note" in lowered:
        document_type = "PACKING_SLIP"
    elif "purchase order" in lowered:
        document_type = "PURCHASE_ORDER"

    return {
        "document_type": document_type,
        "document_number": _first_match(
            [
                r"(?:invoice|document|delivery note|packing slip|purchase order|po)[ \t]*(?:no\.?|number|#)?[ \t]*[:\-]?[ \t]*([A-Z0-9_\-/]+)",
            ],
            normalized,
        ),
        "purchase_order_no": _first_match(
            [r"(?:purchase order|po)[ \t]*(?:no\.?|number|#)?[ \t]*[:\-]?[ \t]*([A-Z0-9_\-/]+)"],
            normalized,
        ),
        "document_date": _first_match(
            [r"(?:invoice date|document date|date)[ \t]*[:\-]?[ \t]*([0-9]{1,4}[./-][0-9]{1,2}[./-][0-9]{1,4})"],
            normalized,
        ),
        "total_amount": _first_match(
            [r"(?:grand total|invoice total|total)[ \t]*[:\-]?[ \t]*(?:EUR|USD|GBP|€|\$)?[ \t]*([0-9.,]+)"],
            normalized,
        ),
    }


def ingest_supplier_document(
    session: Session,
    file_path: str | Path,
    supplier_code: str | None = None,
) -> dict[str, Any]:
    path = Path(file_path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise DocumentExtractionError(f"Document not found: {path}")
    if path.suffix.lower() != ".pdf":
        raise DocumentExtractionError("This reference adapter currently accepts PDF files only")

    supplier_id = None
    if supplier_code:
        supplier_id = session.execute(
            text("SELECT supplier_id FROM inventory.dim_supplier WHERE supplier_code = :supplier_code"),
            {"supplier_code": supplier_code.strip().upper()},
        ).scalar_one_or_none()
        if supplier_id is None:
            raise DocumentExtractionError(f"Unknown supplier_code: {supplier_code}")

    file_hash = _sha256(path)
    existing = session.execute(
        text("SELECT document_id, status FROM inventory.raw_supplier_documents WHERE file_sha256 = :file_hash"),
        {"file_hash": file_hash},
    ).mappings().first()
    if existing:
        return {"document_id": int(existing["document_id"]), "status": existing["status"], "duplicate": True}

    extraction_method = "PDF_TEXT"
    try:
        content, extraction_method = _extract_pdf_text(path)
        parsed = parse_supplier_document(content)
        status = "PARSED" if parsed.get("document_number") or parsed.get("purchase_order_no") else "REVIEW_REQUIRED"
        error_message = None
    except Exception as exc:
        content = ""
        parsed = {}
        status = "FAILED"
        error_message = str(exc)[:4000]

    document_id = session.execute(
        text(
            """
            INSERT INTO inventory.raw_supplier_documents
                (file_name, file_sha256, supplier_id, document_type, extracted_text,
                 parsed_payload, extraction_method, status, error_message)
            VALUES
                (:file_name, :file_sha256, :supplier_id, :document_type, :extracted_text,
                 CAST(:parsed_payload AS JSONB), :extraction_method, :status, :error_message)
            RETURNING document_id
            """
        ),
        {
            "file_name": path.name,
            "file_sha256": file_hash,
            "supplier_id": supplier_id,
            "document_type": parsed.get("document_type", "UNKNOWN"),
            "extracted_text": content,
            "parsed_payload": json.dumps(parsed),
            "extraction_method": extraction_method,
            "status": status,
            "error_message": error_message,
        },
    ).scalar_one()
    session.commit()
    return {
        "document_id": int(document_id),
        "status": status,
        "extraction_method": extraction_method,
        "parsed_payload": parsed,
        "duplicate": False,
    }
