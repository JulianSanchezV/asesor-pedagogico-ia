import io
import zipfile
import xml.etree.ElementTree as ET
from app.services.pdf_parser import extract_pdf_content

SUPPORTED_DOC_EXTENSIONS = (".pdf", ".docx", ".txt", ".md")


def _extract_docx_text(data: bytes) -> str:
    """Extract paragraphs and table cells from a .docx file using Python stdlib (zip + XML)."""
    chunks: list[str] = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        if "word/document.xml" not in zf.namelist():
            raise ValueError("El archivo .docx no contiene word/document.xml válido.")
        xml_bytes = zf.read("word/document.xml")

    root = ET.fromstring(xml_bytes)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

    # Walk body children in order (paragraphs & tables)
    body = root.find("w:body", ns)
    if body is None:
        return ""

    for child in body:
        tag = child.tag.split("}")[-1]
        if tag == "p":
            texts = [t.text for t in child.findall(".//w:t", ns) if t.text]
            line = "".join(texts).strip()
            if line:
                chunks.append(line)
        elif tag == "tbl":
            for row in child.findall(".//w:tr", ns):
                cells = []
                for cell in row.findall(".//w:tc", ns):
                    ctexts = [t.text for t in cell.findall(".//w:t", ns) if t.text]
                    cell_str = " ".join("".join(ctexts).split())
                    if cell_str:
                        cells.append(cell_str)
                if cells:
                    chunks.append(" | ".join(cells))

    return "\n".join(chunks)


def extract_document_content(data: bytes, filename: str, max_images: int = 3) -> dict:
    """
    Universal document extractor supporting .pdf, .docx, .txt and .md.
    Returns {text, page_count, image_count, extracted_images, is_readable, format}.
    """
    lower = (filename or "").lower().strip()

    if lower.endswith(".pdf"):
        info = extract_pdf_content(data, max_images=max_images)
        info["format"] = "pdf"
        return info

    if lower.endswith(".docx"):
        text = _extract_docx_text(data)
        approx_pages = max(1, len(text) // 2500 + 1) if text else 0
        return {
            "text": text,
            "page_count": approx_pages,
            "image_count": 0,
            "extracted_images": [],
            "is_readable": len(text.strip()) >= 20,
            "format": "docx",
        }

    if lower.endswith(".txt") or lower.endswith(".md"):
        text = data.decode("utf-8", errors="replace").strip()
        approx_pages = max(1, len(text) // 2500 + 1) if text else 0
        return {
            "text": text,
            "page_count": approx_pages,
            "image_count": 0,
            "extracted_images": [],
            "is_readable": len(text) >= 20,
            "format": lower.rsplit(".", 1)[-1],
        }

    raise ValueError(
        f"Formato no soportado ({filename}). Formatos permitidos: {', '.join(SUPPORTED_DOC_EXTENSIONS)}"
    )
