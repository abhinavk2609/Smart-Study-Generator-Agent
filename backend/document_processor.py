"""
Document processor — extracts text from PDFs and images uploaded by the user.
Uses PyMuPDF (fitz) for PDFs and Pillow + pytesseract for images (OCR).
Falls back gracefully when optional OCR dependencies are missing.
"""

import io
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency guards
# ---------------------------------------------------------------------------
try:
    import fitz  # PyMuPDF
    _PYMUPDF_AVAILABLE = True
except ImportError:
    _PYMUPDF_AVAILABLE = False
    logger.warning("PyMuPDF not installed — PDF text extraction unavailable.")

try:
    from PIL import Image
    import pytesseract
    _OCR_AVAILABLE = True
except ImportError:
    _OCR_AVAILABLE = False
    logger.warning("Pillow / pytesseract not installed — image OCR unavailable.")


MAX_EXTRACTED_CHARS = 50_000   # cap to stay within model context window


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extract all text from a PDF given its raw bytes.
    Returns extracted text (possibly empty if PDF is image-only).
    """
    if not _PYMUPDF_AVAILABLE:
        return "[PDF processing unavailable: PyMuPDF is not installed]"

    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        parts: list[str] = []
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text("text")
            if text.strip():
                parts.append(f"--- Page {page_num + 1} ---\n{text.strip()}")
        doc.close()
        full_text = "\n\n".join(parts)
        return full_text[:MAX_EXTRACTED_CHARS] if full_text else "[No selectable text found in PDF]"
    except Exception as exc:
        logger.error("PDF extraction failed: %s", exc)
        return f"[PDF extraction error: {exc}]"


def extract_text_from_image(file_bytes: bytes) -> str:
    """
    Run OCR on an image given its raw bytes.
    Returns extracted text or a descriptive error.
    """
    if not _OCR_AVAILABLE:
        return "[Image OCR unavailable: Pillow/pytesseract not installed]"

    try:
        image = Image.open(io.BytesIO(file_bytes))
        text = pytesseract.image_to_string(image)
        return text.strip()[:MAX_EXTRACTED_CHARS] if text.strip() else "[No text detected in image]"
    except Exception as exc:
        logger.error("Image OCR failed: %s", exc)
        return f"[Image OCR error: {exc}]"


def extract_text_from_txt(file_bytes: bytes) -> str:
    """Decode a plain-text or Markdown file."""
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            text = file_bytes.decode(encoding)
            return text[:MAX_EXTRACTED_CHARS]
        except (UnicodeDecodeError, ValueError):
            continue
    return "[Could not decode text file]"


def process_uploaded_file(filename: str, file_bytes: bytes) -> dict:
    """
    Dispatch to the correct extractor based on file extension.

    Returns
    -------
    {
        "filename": str,
        "type":     "pdf" | "image" | "text" | "unknown",
        "text":     str,
        "chars":    int,
    }
    """
    ext = Path(filename).suffix.lower()

    if ext == ".pdf":
        text = extract_text_from_pdf(file_bytes)
        file_type = "pdf"
    elif ext in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        text = extract_text_from_image(file_bytes)
        file_type = "image"
    elif ext in {".txt", ".md"}:
        text = extract_text_from_txt(file_bytes)
        file_type = "text"
    else:
        text = "[Unsupported file type]"
        file_type = "unknown"

    return {
        "filename": filename,
        "type": file_type,
        "text": text,
        "chars": len(text),
    }


def combine_document_texts(documents: list[dict]) -> str:
    """
    Merge extracted texts from multiple documents into a single context string
    suitable for inclusion in a prompt.
    """
    if not documents:
        return ""

    sections: list[str] = []
    for doc in documents:
        header = f"=== Document: {doc['filename']} (type: {doc['type']}) ==="
        sections.append(f"{header}\n{doc['text']}")

    combined = "\n\n".join(sections)
    # Hard cap to avoid exceeding model context
    return combined[:MAX_EXTRACTED_CHARS * 2]
