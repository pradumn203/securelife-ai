"""Unit tests for `PdfIngestor` validation rules.

PDFs are generated on-the-fly with PyMuPDF so the test suite is self-contained
(no binary fixtures in the repo). The side effect of writing to a tmp upload
dir is exercised; tmp_path handles cleanup.
"""
from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from app.services.pdf_ingest import (
    PdfEncryptedError,
    PdfIngestor,
    PdfNotAPdfError,
    PdfTooLargeError,
    PdfTooLongError,
    PdfUnreadableError,
)


def _make_pdf(pages: int = 1, *, encrypted: bool = False, text: str = "hello") -> bytes:
    """Build a PyMuPDF document with `pages` pages and return its bytes."""
    doc = fitz.open()
    try:
        for i in range(pages):
            page = doc.new_page()
            page.insert_text((72, 72), f"{text} page {i + 1}")
        if encrypted:
            # Owner + user password → is_encrypted is True on reopen.
            return doc.tobytes(
                encryption=fitz.PDF_ENCRYPT_AES_256,
                owner_pw="owner",
                user_pw="user",
            )
        return doc.tobytes()
    finally:
        doc.close()


@pytest.fixture()
def upload_dir(tmp_path: Path) -> Path:
    d = tmp_path / "uploads"
    d.mkdir()
    return d


def test_ingests_valid_pdf(upload_dir: Path) -> None:
    ingestor = PdfIngestor(upload_dir=upload_dir)
    pdf_bytes = _make_pdf(pages=3)

    stored = ingestor.ingest(
        file_bytes=pdf_bytes,
        original_filename="policy.pdf",
        content_type="application/pdf",
    )

    assert stored.page_count == 3
    assert stored.size_bytes == len(pdf_bytes)
    assert stored.mime_type == "application/pdf"
    assert stored.original_filename == "policy.pdf"
    assert stored.stored_path.exists()
    assert stored.stored_path.parent == upload_dir
    assert stored.stored_path.suffix == ".pdf"
    # bytes on disk round-trip
    assert stored.stored_path.read_bytes() == pdf_bytes


def test_accepts_pdf_filename_without_pdf_content_type(upload_dir: Path) -> None:
    ingestor = PdfIngestor(upload_dir=upload_dir)
    pdf_bytes = _make_pdf()

    stored = ingestor.ingest(
        file_bytes=pdf_bytes,
        original_filename="policy.PDF",
        content_type="application/octet-stream",
    )
    assert stored.page_count == 1


def test_rejects_non_pdf_content_type_and_name(upload_dir: Path) -> None:
    ingestor = PdfIngestor(upload_dir=upload_dir)
    pdf_bytes = _make_pdf()

    with pytest.raises(PdfNotAPdfError) as exc_info:
        ingestor.ingest(
            file_bytes=pdf_bytes,
            original_filename="policy.docx",
            content_type="application/msword",
        )
    assert exc_info.value.http_status == 415


def test_rejects_empty_upload(upload_dir: Path) -> None:
    ingestor = PdfIngestor(upload_dir=upload_dir)
    with pytest.raises(PdfUnreadableError):
        ingestor.ingest(
            file_bytes=b"",
            original_filename="empty.pdf",
            content_type="application/pdf",
        )


def test_rejects_oversized_pdf(upload_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ingestor = PdfIngestor(upload_dir=upload_dir)
    # Shrink the limit so we don't have to synthesize a 20MB blob.
    monkeypatch.setattr(PdfIngestor, "MAX_SIZE_BYTES", 1_000, raising=True)
    pdf_bytes = _make_pdf(pages=5, text="x" * 500)  # comfortably >1 KB

    with pytest.raises(PdfTooLargeError) as exc_info:
        ingestor.ingest(
            file_bytes=pdf_bytes,
            original_filename="policy.pdf",
            content_type="application/pdf",
        )
    assert exc_info.value.http_status == 413


def test_rejects_encrypted_pdf(upload_dir: Path) -> None:
    ingestor = PdfIngestor(upload_dir=upload_dir)
    pdf_bytes = _make_pdf(encrypted=True)

    with pytest.raises(PdfEncryptedError) as exc_info:
        ingestor.ingest(
            file_bytes=pdf_bytes,
            original_filename="locked.pdf",
            content_type="application/pdf",
        )
    assert "Encrypted" in str(exc_info.value)
    assert exc_info.value.http_status == 400


def test_rejects_too_many_pages(upload_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ingestor = PdfIngestor(upload_dir=upload_dir)
    monkeypatch.setattr(PdfIngestor, "MAX_PAGES", 3, raising=True)
    pdf_bytes = _make_pdf(pages=4)

    with pytest.raises(PdfTooLongError) as exc_info:
        ingestor.ingest(
            file_bytes=pdf_bytes,
            original_filename="long.pdf",
            content_type="application/pdf",
        )
    assert "max 3" in str(exc_info.value)
    assert exc_info.value.http_status == 400


def test_rejects_unreadable_bytes(upload_dir: Path) -> None:
    ingestor = PdfIngestor(upload_dir=upload_dir)
    with pytest.raises(PdfUnreadableError):
        ingestor.ingest(
            file_bytes=b"not a pdf at all" * 20,
            original_filename="broken.pdf",
            content_type="application/pdf",
        )
