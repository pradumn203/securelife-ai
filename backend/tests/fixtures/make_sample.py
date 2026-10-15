"""Generate `sample.pdf` for the acceptance curl test.

Run from the backend directory:

    uv run python tests/fixtures/make_sample.py
"""
from __future__ import annotations

from pathlib import Path

import fitz


def main() -> None:
    doc = fitz.open()
    pages = [
        "SecureLife Insurance Policy Schedule",
        "Policy No: TEST-2026-0001",
        "Insured: Rakesh Kumar",
        "Sum Insured: Rs. 10,00,000",
        "Annual Premium: Rs. 12,500",
    ]
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text)
        page.insert_text((72, 120), "Policy Period: 01-Jan-2026 to 31-Dec-2026")

    out = Path(__file__).parent / "sample.pdf"
    out.write_bytes(doc.tobytes())
    doc.close()
    print(f"wrote {out} ({out.stat().st_size} bytes, {len(pages)} pages)")


if __name__ == "__main__":
    main()
