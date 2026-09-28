"""P1-8 — OCR fallback for scanned tender PDFs.

The existing text parser (pdfplumber in tender_check.py) stays the primary
path. This module is ONLY invoked when a PDF yields too little text (scanned
images). If the OCR stack (tesseract binary + pytesseract + a PDF rasterizer)
is not installed on the machine, every function degrades gracefully and the
caller reports "OCR unavailable on server" instead of failing.

No hard dependency is added to requirements.txt: pytesseract/rasterizers are
optional extras detected at import time.
"""

from __future__ import annotations

import io

OCR_AVAILABLE = False
_UNAVAILABLE_REASON = "OCR stack not installed (pytesseract / tesseract / PDF rasterizer)."

try:  # pragma: no cover - depends on machine
    import pytesseract  # type: ignore
    from pytesseract import TesseractNotFoundError  # type: ignore

    try:
        pytesseract.get_tesseract_version()
        OCR_AVAILABLE = True
    except TesseractNotFoundError:
        _UNAVAILABLE_REASON = "Tesseract binary not found on this machine."
except Exception:
    pytesseract = None  # type: ignore[assignment]

try:  # rasterizer preference: PyMuPDF, then pdf2image+poppler
    import fitz  # type: ignore  # PyMuPDF

    _HAVE_FITZ = True
except Exception:
    _HAVE_FITZ = False

if not _HAVE_FITZ:
    try:
        import pdf2image  # type: ignore

        _HAVE_PDF2IMAGE = True
    except Exception:
        _HAVE_PDF2IMAGE = False
else:
    _HAVE_PDF2IMAGE = False

if OCR_AVAILABLE and not (_HAVE_FITZ or _HAVE_PDF2IMAGE):
    OCR_AVAILABLE = False
    _UNAVAILABLE_REASON = "No PDF rasterizer available (install PyMuPDF or pdf2image+poppler)."


def availability() -> dict:
    return {
        "available": OCR_AVAILABLE,
        "reason": "" if OCR_AVAILABLE else _UNAVAILABLE_REASON,
        "rasterizer": "pymupdf" if _HAVE_FITZ else ("pdf2image" if _HAVE_PDF2IMAGE else "none"),
    }


def _rasterize(pdf_bytes: bytes, max_pages: int, dpi: int = 200) -> list:
    """Render PDF pages to PIL images."""
    from PIL import Image  # noqa: F401  (ensures PIL present for pytesseract)

    if _HAVE_FITZ:
        images = []
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for page in doc.pages(count=max_pages) if hasattr(doc, "pages") else list(doc)[:max_pages]:
                pix = page.get_pixmap(dpi=dpi)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples) \
                    if hasattr(pix, "samples") else None
                if img is not None:
                    images.append(img)
        return images

    if _HAVE_PDF2IMAGE:
        return pdf2image.convert_from_bytes(pdf_bytes, dpi=dpi, first_page=1, last_page=max_pages)

    return []


def ocr_pdf(pdf_bytes: bytes, max_pages: int = 40) -> dict:
    """OCR a scanned PDF.

    Returns {'used': bool, 'pages': int, 'text': str, 'confidence': float|None,
             'message': str}. On any failure, used=False with an honest message
    and the caller keeps its existing 'unparseable' handling.
    """
    if not OCR_AVAILABLE:
        return {
            "used": False, "pages": 0, "text": "", "confidence": None,
            "message": f"OCR unavailable on server ({_UNAVAILABLE_REASON})",
        }

    try:
        images = _rasterize(pdf_bytes, max_pages)
    except Exception as exc:
        return {
            "used": False, "pages": 0, "text": "", "confidence": None,
            "message": f"OCR failed while rendering the document ({type(exc).__name__}).",
        }

    if not images:
        return {
            "used": False, "pages": 0, "text": "", "confidence": None,
            "message": "OCR could not render any pages from this document.",
        }

    texts: list[str] = []
    confs: list[float] = []
    for img in images:
        try:
            texts.append(pytesseract.image_to_string(img) or "")
            try:
                data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                word_confs = [float(c) for c in data.get("conf", [])
                              if c not in ("-1", -1, None) and float(c) >= 0]
                if word_confs:
                    confs.append(sum(word_confs) / len(word_confs))
            except Exception:
                pass
        except Exception:
            texts.append("")

    full_text = "\n".join(t for t in texts if t)
    avg_conf = round(sum(confs) / len(confs), 1) if confs else None
    used = len(full_text.strip()) > 40
    message = (
        f"OCR complete - {len(images)} page(s) processed."
        if used else
        "OCR ran but produced too little text from this document."
    )
    return {
        "used": used,
        "pages": len(images),
        "text": full_text if used else "",
        "confidence": avg_conf,
        "message": message,
    }
