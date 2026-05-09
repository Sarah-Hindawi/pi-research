"""
Claude Vision PDF extractor for medical bills and scanned court docs.

Usage:
    from ingestion.pdf_extractor import extract_pdf
    result = extract_pdf("path/to/medical_bill.pdf")
    # returns: {"text": str, "structured": dict}
"""
import base64
import sys
import os
from pathlib import Path

import pdfplumber
from pdf2image import convert_from_path
from PIL import Image
import io

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from llm_client import get_llm
from config import get_settings

settings = get_settings()

# Minimum chars from pdfplumber before we fall back to vision
TEXT_QUALITY_THRESHOLD = 150


def _pdf_to_images_b64(pdf_path: str) -> list[str]:
    """Convert each PDF page to a base64-encoded JPEG."""
    pages = convert_from_path(pdf_path, dpi=200)
    result = []
    for page in pages:
        buf = io.BytesIO()
        page.save(buf, format="JPEG", quality=85)
        b64 = base64.b64encode(buf.getvalue()).decode()
        result.append(b64)
    return result


def _extract_with_pdfplumber(pdf_path: str) -> str:
    """Try to extract text directly - works for machine-readable PDFs."""
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
    return "\n".join(text_parts).strip()


def _extract_with_vision(pdf_path: str, doc_type: str = "legal") -> dict:
    """
    Use Claude Vision to OCR a scanned PDF.
    doc_type: "legal" | "medical_bill"
    """
    llm = get_llm()
    pages_b64 = _pdf_to_images_b64(pdf_path)

    if doc_type == "medical_bill":
        prompt = (
            "This is a medical bill. Extract ALL information as JSON with keys: "
            "provider_name, patient_name, date_of_service, line_items (array of "
            "{description, cpt_code, amount}), total_amount, insurance_paid, "
            "balance_owing. Return only valid JSON, no other text."
        )
    else:
        prompt = (
            "This is a legal document. Extract all text exactly as it appears. "
            "Preserve paragraph structure. Return plain text only."
        )

    full_text = []
    structured = {}

    for i, b64 in enumerate(pages_b64):
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        response = llm.invoke(messages)

        if doc_type == "medical_bill" and i == 0:
            import json
            try:
                clean = response.strip().removeprefix("```json").removesuffix("```").strip()
                structured = json.loads(clean)
            except Exception:
                structured = {"raw": response}
        else:
            full_text.append(response)

    return {
        "text": "\n\n".join(full_text),
        "structured": structured,
        "pages": len(pages_b64),
    }


def extract_pdf(pdf_path: str, doc_type: str = "legal") -> dict:
    """
    Smart extractor - tries pdfplumber first, falls back to Claude Vision.

    Args:
        pdf_path: path to the PDF file
        doc_type: "legal" | "medical_bill"

    Returns:
        dict with keys:
            text: str - full extracted text
            structured: dict - parsed fields (medical bills only)
            method: str - "pdfplumber" | "vision"
            pages: int
    """
    # Try cheap text extraction first
    direct_text = _extract_with_pdfplumber(pdf_path)

    if len(direct_text) >= TEXT_QUALITY_THRESHOLD:
        return {
            "text": direct_text,
            "structured": {},
            "method": "pdfplumber",
            "pages": None,
        }

    # Fall back to Claude Vision
    print(f"  [pdf_extractor] pdfplumber got {len(direct_text)} chars - using Vision")
    result = _extract_with_vision(pdf_path, doc_type=doc_type)
    result["method"] = "vision"
    return result


if __name__ == "__main__":
    # Quick test - pass a PDF path as argument
    import sys
    if len(sys.argv) < 2:
        print("Usage: python pdf_extractor.py <path_to_pdf> [legal|medical_bill]")
        sys.exit(1)
    path = sys.argv[1]
    dtype = sys.argv[2] if len(sys.argv) > 2 else "legal"
    out = extract_pdf(path, doc_type=dtype)
    print(f"Method: {out['method']} | Pages: {out.get('pages')}")
    print(out["text"][:500])
    if out["structured"]:
        import json
        print("\nStructured:", json.dumps(out["structured"], indent=2))
