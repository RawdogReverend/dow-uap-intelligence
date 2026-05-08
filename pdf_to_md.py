#!/usr/bin/env python3
"""
Convert DOW UFO Release 1 PDFs to Markdown with OCR fallback.

Strategy per PDF:
  1. Try pymupdf4llm — fast, preserves structure for text-layer PDFs.
  2. If extracted text is too sparse (< 100 chars/page avg), fall back to
     Tesseract OCR page-by-page and stitch into plain markdown.

Usage:
    python3 pdf_to_md.py [pdf_dir] [output_dir] [--jobs N]

Defaults:
    pdf_dir    = <project>/data/pdfs
    output_dir = <project>/data/markdown
    jobs       = 4
"""

import argparse
import re
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

MIN_CHARS_PER_PAGE = 100  # below this → OCR fallback


def has_text_layer(pdf_path: Path) -> bool:
    import fitz
    doc = fitz.open(str(pdf_path))
    total = sum(len(page.get_text()) for page in doc)
    pages = max(doc.page_count, 1)
    doc.close()
    return (total / pages) >= MIN_CHARS_PER_PAGE


def extract_with_pymupdf4llm(pdf_path: Path) -> str:
    import pymupdf4llm
    return pymupdf4llm.to_markdown(str(pdf_path))


def extract_with_tesseract(pdf_path: Path) -> str:
    import fitz
    import pytesseract
    from PIL import Image
    import io

    doc = fitz.open(str(pdf_path))
    parts = []
    for i, page in enumerate(doc, 1):
        mat = fitz.Matrix(300 / 72, 300 / 72)  # 300 dpi
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        text = pytesseract.image_to_string(img, lang="eng").strip()
        if text:
            parts.append(f"<!-- page {i} -->\n\n{text}")
    doc.close()
    return "\n\n---\n\n".join(parts)


def clean_markdown(text: str) -> str:
    # Collapse 3+ blank lines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def convert_pdf(pdf_path: Path, out_dir: Path) -> tuple[str, str]:
    """Returns (filename, status)."""
    md_path = out_dir / (pdf_path.stem + ".md")
    if md_path.exists():
        return pdf_path.name, "skipped"

    try:
        if has_text_layer(pdf_path):
            md = extract_with_pymupdf4llm(pdf_path)
            method = "text"
        else:
            md = extract_with_tesseract(pdf_path)
            method = "ocr"

        md = clean_markdown(md)
        if not md:
            return pdf_path.name, "empty"

        # Prepend a title header
        header = f"# {pdf_path.stem}\n\n"
        md_path.write_text(header + md, encoding="utf-8")
        return pdf_path.name, f"ok ({method})"

    except Exception as e:
        return pdf_path.name, f"ERROR: {e}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    base = Path(__file__).parent / "data"
    parser.add_argument("pdf_dir",    nargs="?", default=str(base / "pdfs"))
    parser.add_argument("output_dir", nargs="?", default=str(base / "markdown"))
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()

    pdf_dir = Path(args.pdf_dir)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {pdf_dir}")
        sys.exit(1)

    print(f"Found {len(pdfs)} PDFs")
    print(f"Output: {out_dir}")
    print(f"Workers: {args.jobs}\n")

    counts = {"ok (text)": 0, "ok (ocr)": 0, "skipped": 0, "empty": 0, "error": 0}

    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(convert_pdf, p, out_dir): p for p in pdfs}
        for i, fut in enumerate(as_completed(futures), 1):
            name, status = fut.result()
            tag = "error" if status.startswith("ERROR") else status.split()[0] if "ok" not in status else ("ok (text)" if "text" in status else "ok (ocr)")
            counts[tag] = counts.get(tag, 0) + 1
            print(f"  [{i:3}/{len(pdfs)}] {status:<20} {name}")

    print(f"\n=== Done ===")
    for k, v in counts.items():
        if v:
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
