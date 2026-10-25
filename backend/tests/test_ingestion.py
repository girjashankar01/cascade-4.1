"""Tests for evidence ingestion, PDF parsing, OCR fallback, and idempotency."""

from pathlib import Path
import pytest

from app.db import init_db
from app.ingestion.ocr import set_ocr_mock_handler
from app.ingestion.pdf import (
    EmptyDocumentError,
    MalformedDocumentError,
    UnsupportedFormatError,
    extract_pdf_pages,
    ingest_source,
)


@pytest.fixture
def temp_env(tmp_path: Path):
    db_file = tmp_path / "test.db"
    init_db(db_file)
    storage_dir = tmp_path / "sources"
    yield db_file, storage_dir
    set_ocr_mock_handler(None)


def test_digital_pdf_native_text_extraction(temp_env):
    db_file, storage_dir = temp_env
    fixture_pdf = Path(__file__).resolve().parents[2] / "fixtures" / "proposal.pdf"
    raw_bytes = fixture_pdf.read_bytes()

    pages, ocr_used = extract_pdf_pages(raw_bytes)
    assert 1 in pages
    assert "$5.0M" in pages[1]
    assert "0x9965507D1a55BCC6475675304Ca994970De97744" in pages[1]
    assert ocr_used is False


def test_plain_text_ingestion_page_1(temp_env):
    db_file, storage_dir = temp_env
    content = "Discussion on proposal: allocation is $5.8M."
    meta = ingest_source(
        raw_bytes=content.encode("utf-8"),
        filename="forum.txt",
        content_type="text/plain",
        storage_dir=storage_dir,
        db_path=db_file,
    )
    assert meta["page_count"] == 1
    assert 1 in meta["extracted_pages"]
    assert meta["extracted_pages"][1] == content
    assert meta["ocr_used"] is False


def test_ocr_fallback_threshold(temp_env):
    db_file, storage_dir = temp_env
    import pymupdf

    # Create a PDF with almost no text (< 50 chars)
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text(pymupdf.Point(50, 72), "Hi", fontsize=10)
    pdf_bytes = doc.tobytes()
    doc.close()

    # Mock OCR handler
    mock_ocr_called = False

    def mock_ocr(image_bytes: bytes):
        nonlocal mock_ocr_called
        mock_ocr_called = True
        return "Scanned text from OCR: budget is $1,000,000", 0.92

    set_ocr_mock_handler(mock_ocr)

    pages, ocr_used = extract_pdf_pages(pdf_bytes, ocr_threshold=50)
    assert mock_ocr_called is True
    assert ocr_used is True
    assert "budget is $1,000,000" in pages[1]


def test_empty_document_error(temp_env):
    db_file, storage_dir = temp_env
    with pytest.raises(EmptyDocumentError):
        ingest_source(b"", "empty.txt", storage_dir=storage_dir, db_path=db_file)

    with pytest.raises(EmptyDocumentError):
        ingest_source(b"   \n  ", "spaces.txt", storage_dir=storage_dir, db_path=db_file)


def test_malformed_document_error(temp_env):
    db_file, storage_dir = temp_env
    with pytest.raises(MalformedDocumentError):
        ingest_source(b"not a valid pdf", "corrupt.pdf", content_type="application/pdf", storage_dir=storage_dir, db_path=db_file)


def test_unsupported_format_error(temp_env):
    db_file, storage_dir = temp_env
    with pytest.raises(UnsupportedFormatError):
        ingest_source(b"audio binary data", "song.mp3", content_type="audio/mpeg", storage_dir=storage_dir, db_path=db_file)


def test_idempotent_ingestion(temp_env):
    db_file, storage_dir = temp_env
    content = "Stable proposal text for idempotency check."
    meta1 = ingest_source(
        raw_bytes=content.encode("utf-8"),
        filename="stable.txt",
        content_type="text/plain",
        storage_dir=storage_dir,
        db_path=db_file,
    )
    meta2 = ingest_source(
        raw_bytes=content.encode("utf-8"),
        filename="stable.txt",
        content_type="text/plain",
        storage_dir=storage_dir,
        db_path=db_file,
    )

    assert meta1["id"] == meta2["id"]
    assert meta1["sha256"] == meta2["sha256"]
    assert meta1["created_at"] == meta2["created_at"]
