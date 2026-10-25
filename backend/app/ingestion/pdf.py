"""PDF and plain-text ingestion engine with PyMuPDF native extraction and OCR fallback."""

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pymupdf

from app.db import get_db_connection
from app.ingestion.ocr import ocr_page_bytes

logger = logging.getLogger(__name__)

MIN_USABLE_TEXT_LENGTH = 50
DEFAULT_STORAGE_DIR = Path(__file__).resolve().parents[2] / "data" / "sources"


class IngestionError(Exception):
    """Base class for ingestion errors."""


class EmptyDocumentError(IngestionError):
    """Raised when uploaded file or text is empty."""


class MalformedDocumentError(IngestionError):
    """Raised when document cannot be parsed or opened."""


class UnsupportedFormatError(IngestionError):
    """Raised when file format is not supported."""


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal and unsafe characters."""
    clean = Path(filename).name
    clean = re.sub(r"[^\w\.\-]", "_", clean)
    return clean or "unnamed_source"


def extract_pdf_pages(
    file_bytes: bytes,
    ocr_threshold: int = MIN_USABLE_TEXT_LENGTH,
) -> Tuple[Dict[int, str], bool]:
    """Extract text from PDF pages (1-indexed) using PyMuPDF native text, with OCR fallback.

    Returns (pages_dict, ocr_used).
    """
    if not file_bytes:
        raise EmptyDocumentError("Empty PDF file bytes")

    try:
        doc = pymupdf.open(stream=file_bytes, filetype="pdf")
    except Exception as e:
        raise MalformedDocumentError(f"Failed to parse PDF document: {e}") from e

    try:
        page_count = len(doc)
        if page_count == 0:
            raise EmptyDocumentError("PDF document has 0 pages")

        pages: Dict[int, str] = {}
        ocr_used = False

        for page_idx in range(page_count):
            page_num = page_idx + 1
            page = doc[page_idx]
            text = page.get_text() or ""
            clean_text = text.strip()

            if len(clean_text) < ocr_threshold:
                # Trigger OCR fallback for low-text / scanned page
                try:
                    pix = page.get_pixmap(dpi=150)
                    img_bytes = pix.tobytes("png")
                    ocr_text, ocr_conf = ocr_page_bytes(img_bytes)
                    if ocr_text.strip():
                        clean_text = ocr_text.strip()
                        ocr_used = True
                        logger.info(f"OCR extracted {len(clean_text)} chars on page {page_num} (conf: {ocr_conf:.2f})")
                except Exception as ocr_err:
                    logger.warning(f"OCR fallback failed on page {page_num}: {ocr_err}")

            pages[page_num] = clean_text

        # Verify that document is not completely blank across all pages
        total_text = "".join(pages.values()).strip()
        if not total_text:
            raise EmptyDocumentError("Extracted text is empty across all pages")

        return pages, ocr_used
    finally:
        doc.close()


def ingest_source(
    raw_bytes: bytes,
    filename: str,
    content_type: Optional[str] = None,
    storage_dir: Optional[Path] = None,
    db_path: Optional[Path | str] = None,
    ocr_threshold: int = MIN_USABLE_TEXT_LENGTH,
) -> Dict[str, Any]:
    """Ingest a source file (PDF or plain text) idempotently, persisting metadata and extracted text.

    Returns the source metadata dict.
    """
    if not raw_bytes or not raw_bytes.strip():
        raise EmptyDocumentError("Source content is empty")

    sha256 = hashlib.sha256(raw_bytes).hexdigest()
    clean_name = sanitize_filename(filename)

    # Check if this exact source hash was already ingested (idempotent ingestion)
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sources WHERE sha256 = ?", (sha256,))
        row = cursor.fetchone()
        if row:
            return {
                "id": row["id"],
                "sha256": row["sha256"],
                "filename": row["filename"],
                "content_type": row["content_type"],
                "storage_path": row["storage_path"],
                "page_count": row["page_count"],
                "extracted_pages": json.loads(row["extracted_pages"]),
                "ocr_used": bool(row["ocr_used"]),
                "created_at": row["created_at"],
            }

    # Determine type and extract
    inferred_type = content_type or ""
    is_pdf = clean_name.lower().endswith(".pdf") or "pdf" in inferred_type.lower() or raw_bytes.startswith(b"%PDF")

    if is_pdf:
        content_type = "application/pdf"
        pages, ocr_used = extract_pdf_pages(raw_bytes, ocr_threshold=ocr_threshold)
    elif clean_name.lower().endswith(".txt") or "text" in inferred_type.lower() or not inferred_type:
        content_type = "text/plain"
        try:
            text = raw_bytes.decode("utf-8").strip()
        except UnicodeDecodeError as e:
            raise MalformedDocumentError(f"Plain text is not valid UTF-8: {e}") from e
        if not text:
            raise EmptyDocumentError("Plain text source is empty")
        pages = {1: text}
        ocr_used = False
    else:
        raise UnsupportedFormatError(f"Unsupported file format: {clean_name} ({inferred_type})")

    # Persist raw bytes to disk
    target_dir = storage_dir or DEFAULT_STORAGE_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    stored_file_path = target_dir / f"{sha256}_{clean_name}"
    if not stored_file_path.exists():
        with open(stored_file_path, "wb") as f:
            f.write(raw_bytes)

    source_id = f"src_{sha256[:12]}"
    created_at = datetime.now(timezone.utc).isoformat()
    pages_json = json.dumps({str(k): v for k, v in pages.items()})

    with get_db_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO sources (id, sha256, filename, content_type, storage_path, page_count, extracted_pages, ocr_used, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                sha256,
                clean_name,
                content_type,
                str(stored_file_path),
                len(pages),
                pages_json,
                int(ocr_used),
                created_at,
            ),
        )

    return {
        "id": source_id,
        "sha256": sha256,
        "filename": clean_name,
        "content_type": content_type,
        "storage_path": str(stored_file_path),
        "page_count": len(pages),
        "extracted_pages": pages,
        "ocr_used": ocr_used,
        "created_at": created_at,
    }
