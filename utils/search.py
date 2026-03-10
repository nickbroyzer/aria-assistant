"""
Web search and PDF processing utilities.
"""

import base64
import io

import fitz  # PyMuPDF
import pdfplumber
from duckduckgo_search import DDGS


def web_search(query: str, max_results: int = 5) -> str:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return "No results found."
        formatted = []
        for r in results:
            formatted.append(f"Title: {r['title']}\nSummary: {r['body']}\nSource: {r['href']}")
        return "\n\n".join(formatted)
    except Exception as e:
        return f"Search failed: {str(e)}"


def process_pdf(pdf_bytes: bytes) -> dict:
    """Extract text and/or render pages as images from a PDF.
    Returns { text, images: [base64, ...] }
    """
    # Extract text
    text = ""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages_text = [p.extract_text() or "" for p in pdf.pages]
            text = "\n\n".join(pages_text).strip()
    except Exception:
        pass

    # Render pages as images (up to 4 pages)
    images = []
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for i, page in enumerate(doc):
            if i >= 4:
                break
            mat = fitz.Matrix(1.5, 1.5)  # 1.5x zoom for clarity
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")
            images.append(base64.b64encode(img_bytes).decode("utf-8"))
        doc.close()
    except Exception:
        pass

    return {"text": text, "images": images}
