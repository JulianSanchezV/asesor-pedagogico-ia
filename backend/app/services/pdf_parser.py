import fitz  # PyMuPDF


def extract_pdf_content(pdf_bytes: bytes, max_images: int = 3) -> dict:
    """
    Extract readable text and embedded diagrams/images from a student PDF report.
    Supports multimodal analysis (text + images/diagrams) with Gemini.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages_text: list[str] = []
    images_bytes: list[tuple[bytes, str]] = []
    total_images = 0

    try:
        for idx, page in enumerate(doc):
            text = page.get_text("text").strip()
            if text:
                pages_text.append(f"--- Página {idx + 1} ---\n{text}")

            page_images = page.get_images(full=True)
            total_images += len(page_images)
            for img_info in page_images:
                if len(images_bytes) >= max_images:
                    break
                xref = img_info[0]
                try:
                    base_img = doc.extract_image(xref)
                    ext = base_img.get("ext", "png").lower()
                    mime = f"image/{'jpeg' if ext == 'jpg' else ext}"
                    img_data = base_img.get("image")
                    if img_data and len(img_data) < 2_500_000:
                        images_bytes.append((img_data, mime))
                except Exception:
                    continue

        full_text = "\n\n".join(pages_text)
        return {
            "text": full_text,
            "page_count": len(doc),
            "image_count": total_images,
            "extracted_images": images_bytes,
            "is_readable": len(full_text.strip()) >= 30,
        }
    finally:
        doc.close()
